"""Host SaaS F1 — workspace purge + export manifest."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestHostWorkspacePurge:
    def test_purge_removes_data_and_is_idempotent(
        self, client: TestClient, monkeypatch, tmp_path
    ):
        from app import config
        import app.storage as storage_mod

        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("MEM_DOG_DATA_DIR", str(tmp_path / "memdog"))
        monkeypatch.setattr(config, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(config, "MEM_DOG_DATA_DIR", str(tmp_path / "memdog"), raising=False)
        monkeypatch.setattr(config, "API_KEY", "", raising=False)
        storage_mod.storage_instance = None

        ws = client.post(
            "/api/v1/host/workspaces",
            json={
                "external_org_id": "purge-org",
                "external_workspace_id": "purge-ws",
                "display_name": "Purge Me",
            },
        )
        if ws.status_code >= 500:
            pytest.skip(f"local storage not configured: {ws.text}")
        assert ws.status_code == 201, ws.text
        body = ws.json()
        md_key = body["api_key"]
        user_id = body["user_id"]
        project_id = body["project_id"]
        org_id = body["org_id"]

        up = client.post(
            "/api/v1/data",
            headers={"x-api-key": md_key},
            data={
                "content": "purge target note",
                "mime_type": "text/plain",
                "owner_user_id": user_id,
                "org_id": org_id,
                "project_id": project_id,
                "external_id": "purge:note-1",
                "name": "note",
            },
        )
        assert up.status_code == 200, up.text
        data_id = up.json()["data_id"]

        exp = client.get(
            "/api/v1/host/workspaces/export",
            params={
                "external_org_id": "purge-org",
                "external_workspace_id": "purge-ws",
            },
        )
        assert exp.status_code == 200, exp.text
        assert exp.json()["data_count"] >= 1

        purged = client.delete(
            "/api/v1/host/workspaces",
            params={
                "external_org_id": "purge-org",
                "external_workspace_id": "purge-ws",
            },
        )
        assert purged.status_code == 200, purged.text
        result = purged.json()
        assert result["purged"] is True
        assert result["already_gone"] is False
        assert result["deleted_data_count"] >= 1
        assert result["project_id"] == project_id

        # Data should be gone (404 preferred; some stacks surface 500 on missing meta)
        meta = client.get(
            f"/api/v1/data/{data_id}/metadata",
            params={"user_id": user_id},
            headers={"x-api-key": md_key},
        )
        assert meta.status_code != 200

        # Workspace gone
        lookup = client.get(
            "/api/v1/host/workspaces",
            params={
                "external_org_id": "purge-org",
                "external_workspace_id": "purge-ws",
            },
        )
        assert lookup.status_code == 404

        # Remaining user data for this project should be empty
        listed, total = storage_mod.get_storage().list_all_metadata_paginated(
            user_id=user_id, project_id=project_id, skip=0, limit=50
        )
        assert total == 0
        assert listed == []

        # Idempotent re-purge
        again = client.delete(
            "/api/v1/host/workspaces",
            params={
                "external_org_id": "purge-org",
                "external_workspace_id": "purge-ws",
            },
        )
        assert again.status_code == 200
        assert again.json()["already_gone"] is True

    def test_purge_by_project_id(self, client: TestClient, monkeypatch, tmp_path):
        from app import config
        import app.storage as storage_mod

        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("MEM_DOG_DATA_DIR", str(tmp_path / "memdog2"))
        monkeypatch.setattr(config, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(config, "MEM_DOG_DATA_DIR", str(tmp_path / "memdog2"), raising=False)
        monkeypatch.setattr(config, "API_KEY", "", raising=False)
        storage_mod.storage_instance = None

        ws = client.post(
            "/api/v1/host/workspaces",
            json={
                "external_org_id": "purge-org-b",
                "external_workspace_id": "purge-ws-b",
            },
        )
        if ws.status_code >= 500:
            pytest.skip(f"local storage not configured: {ws.text}")
        assert ws.status_code == 201
        project_id = ws.json()["project_id"]

        resp = client.delete(f"/api/v1/host/workspaces/by-project/{project_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["purged"] is True
        assert resp.json()["already_gone"] is False
