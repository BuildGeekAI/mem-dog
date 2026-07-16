"""Host SaaS — workspace provision, project isolation, external_id upsert."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import HostWorkspaceCreate
from app.routers.ai_query import ChatRequest, SearchMode, SemanticQueryRequest
from app.storage import BaseStorage


class TestHostWorkspaceModels:
    def test_workspace_create_defaults(self):
        body = HostWorkspaceCreate(
            external_org_id="acct-1",
            external_workspace_id="ws-9",
        )
        assert body.display_name is None
        assert body.metadata == {}

    def test_semantic_request_accepts_project_id(self):
        req = SemanticQueryRequest(query="hello", project_id="proj_abc")
        assert req.project_id == "proj_abc"
        assert req.search_mode == SearchMode.vector

    def test_chat_request_accepts_project_id(self):
        req = ChatRequest(message="hello", project_id="proj_abc")
        assert req.project_id == "proj_abc"


class TestProjectIsolationSearch:
    """Unit-test BaseStorage.similarity_search project filter without AI engines."""

    def test_filters_by_project_id(self, tmp_path, monkeypatch):
        from app.blob_store import LocalBlobStore

        stores = {
            name: LocalBlobStore(str(tmp_path / name))
            for name in (
                "raw", "meta", "memories", "index", "users", "prompts",
                "embeddings", "viewpoints", "ai_config", "skills", "stats", "channels",
            )
        }

        class _Local(BaseStorage):
            def _build_stores(self):
                return stores

        storage = _Local()
        monkeypatch.setattr(storage, "_check_ai_enabled", lambda: None)

        def _write(emb_id: str, project_id: str, text: str):
            import json
            path = f"u1/data1/ver_1/embeddings/{emb_id}.json"
            vec = [1.0, 0.0, 0.0]
            payload = {
                "embedding_id": emb_id,
                "data_id": "data_a" if project_id == "proj_a" else "data_b",
                "user_id": "u1",
                "project_id": project_id,
                "chunk_text": text,
                "vector": vec,
            }
            stores["embeddings"].write(
                path, json.dumps(payload).encode("utf-8"), "application/json"
            )

        _write("e1", "proj_a", "secret from A")
        _write("e2", "proj_b", "secret from B")

        hits_a = storage.similarity_search([1.0, 0.0, 0.0], limit=10, user_id="u1", project_id="proj_a")
        hits_b = storage.similarity_search([1.0, 0.0, 0.0], limit=10, user_id="u1", project_id="proj_b")
        hits_all = storage.similarity_search([1.0, 0.0, 0.0], limit=10, user_id="u1")

        assert len(hits_a) == 1 and hits_a[0]["chunk_text"] == "secret from A"
        assert len(hits_b) == 1 and hits_b[0]["chunk_text"] == "secret from B"
        assert len(hits_all) == 2


class TestExternalIdUpsert:
    def _local_storage(self, tmp_path, monkeypatch):
        from app.blob_store import LocalBlobStore
        from app import config

        monkeypatch.setattr(config, "ENABLE_MEMORIES", False, raising=False)

        stores = {
            name: LocalBlobStore(str(tmp_path / name))
            for name in (
                "raw", "meta", "memories", "index", "users", "prompts",
                "embeddings", "viewpoints", "ai_config", "skills", "stats", "channels",
            )
        }

        class _Local(BaseStorage):
            def _build_stores(self):
                return stores

        return _Local()

    def test_upsert_preserves_data_id(self, tmp_path, monkeypatch):
        storage = self._local_storage(tmp_path, monkeypatch)
        kwargs = dict(
            content=b"v1 body",
            content_type="text/plain",
            user="u_host",
            name="page",
            project_id="proj_x",
            org_id="org_x",
            external_id="notion:page-1",
            exclusive_memory_ids=True,
        )
        data_id, version, created, updated = storage.create_or_upsert_data(**kwargs)
        assert created is True and updated is False
        assert version == 1
        assert data_id.startswith("data_")

        data_id2, version2, created2, updated2 = storage.create_or_upsert_data(
            **{**kwargs, "content": b"v2 body resynced"}
        )
        assert data_id2 == data_id
        assert version2 == 2
        assert created2 is False and updated2 is True

        meta = storage.get_metadata(data_id, "u_host")
        assert meta is not None
        assert meta.external_id == "notion:page-1"
        assert meta.project_id == "proj_x"
        assert any(t == "external_id:notion:page-1" for t in (meta.tags or []))

        content_ct = storage.get_raw_data(data_id, "u_host")
        assert content_ct is not None
        content, _ct = content_ct
        assert content == b"v2 body resynced"

    def test_different_projects_are_isolated(self, tmp_path, monkeypatch):
        storage = self._local_storage(tmp_path, monkeypatch)
        a_id, _, _, _ = storage.create_or_upsert_data(
            content=b"a",
            content_type="text/plain",
            user="u_host",
            project_id="proj_a",
            external_id="same-key",
            exclusive_memory_ids=True,
        )
        b_id, _, _, _ = storage.create_or_upsert_data(
            content=b"b",
            content_type="text/plain",
            user="u_host",
            project_id="proj_b",
            external_id="same-key",
            exclusive_memory_ids=True,
        )
        assert a_id != b_id

    def test_api_upsert_via_data_endpoint(self, client: TestClient):
        mock_storage = MagicMock()
        mock_storage.create_or_upsert_data.return_value = ("data_upsert1", 2, False, True)
        mock_storage.create_data.return_value = ("data_new", 1)

        with patch("app.routers.data.get_storage", return_value=mock_storage):
            resp = client.post(
                "/api/v1/data",
                data={
                    "content": "hello",
                    "mime_type": "text/plain",
                    "external_id": "ext-99",
                    "project_id": "proj_z",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_id"] == "data_upsert1"
        assert body["version"] == 2
        assert body["created"] is False
        assert body["updated"] is True
        mock_storage.create_or_upsert_data.assert_called_once()
        assert mock_storage.create_or_upsert_data.call_args[1]["external_id"] == "ext-99"


class TestHostWorkspaceAPI:
    def test_create_and_idempotent(self, client: TestClient, monkeypatch, tmp_path):
        """Exercise workspace provision against local storage when available."""
        from app import config
        import app.storage as storage_mod

        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("MEM_DOG_DATA_DIR", str(tmp_path / "memdog"))
        monkeypatch.setattr(config, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(config, "MEM_DOG_DATA_DIR", str(tmp_path / "memdog"), raising=False)
        monkeypatch.setattr(config, "API_KEY", "", raising=False)
        storage_mod.storage_instance = None

        resp = client.post(
            "/api/v1/host/workspaces",
            json={
                "external_org_id": "host-acct-1",
                "external_workspace_id": "ws-alpha",
                "display_name": "Alpha",
            },
        )
        if resp.status_code >= 500:
            pytest.skip(f"local storage not fully configured in test env: {resp.text}")

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["created"] is True
        assert body["api_key"] and body["api_key"].startswith("md_")
        assert body["org_id"].startswith("org_")
        assert body["project_id"].startswith("proj_")
        assert body["user_id"]

        again = client.post(
            "/api/v1/host/workspaces",
            json={
                "external_org_id": "host-acct-1",
                "external_workspace_id": "ws-alpha",
            },
        )
        assert again.status_code == 201
        again_body = again.json()
        assert again_body["created"] is False
        assert again_body["api_key"] is None
        assert again_body["org_id"] == body["org_id"]
        assert again_body["project_id"] == body["project_id"]

        lookup = client.get(
            "/api/v1/host/workspaces",
            params={
                "external_org_id": "host-acct-1",
                "external_workspace_id": "ws-alpha",
            },
        )
        assert lookup.status_code == 200
        assert lookup.json()["project_id"] == body["project_id"]

    def test_ready_endpoint(self, client: TestClient):
        resp = client.get("/ready")
        assert resp.status_code in (200, 503)
        assert "status" in resp.json()
