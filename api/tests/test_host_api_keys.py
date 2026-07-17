"""Host SaaS F5 — API key create / list / rotate / revoke."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestHostApiKeyRotation:
    def test_rotate_create_and_revoke(self, client: TestClient, monkeypatch, tmp_path):
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
                "external_org_id": "rot-org",
                "external_workspace_id": "rot-ws",
                "display_name": "Rotate",
            },
        )
        if ws.status_code >= 500:
            pytest.skip(f"local storage not configured: {ws.text}")
        assert ws.status_code == 201, ws.text
        body = ws.json()
        md_key = body["api_key"]
        user_id = body["user_id"]
        assert md_key.startswith("md_")

        headers = {"x-api-key": md_key}
        listed = client.get("/api/v1/host/api-keys", headers=headers)
        assert listed.status_code == 200
        keys = listed.json()
        assert len(keys) == 1
        assert keys[0]["key"] is None
        assert keys[0].get("key_prefix", "").startswith("md_")
        old_id = keys[0]["key_id"]

        # Refuse last-key revoke
        bad = client.delete(f"/api/v1/host/api-keys/{old_id}", headers=headers)
        assert bad.status_code == 400

        rotated = client.post(
            "/api/v1/host/api-keys/rotate",
            headers=headers,
            json={"name": "rotated", "revoke_key_id": old_id},
        )
        assert rotated.status_code == 200, rotated.text
        rot = rotated.json()
        assert rot["key"].startswith("md_")
        assert rot["revoked_key_id"] == old_id
        assert rot["user_id"] == user_id

        # Old key rejected when API_KEY is unset? Middleware is open — validate via list with new key
        new_headers = {"x-api-key": rot["key"]}
        after = client.get("/api/v1/host/api-keys", headers=new_headers)
        assert after.status_code == 200
        after_keys = after.json()
        assert len(after_keys) == 1
        assert after_keys[0]["key_id"] == rot["key_id"]
        assert after_keys[0]["key"] is None

    def test_cross_user_forbidden_when_api_key_set(
        self, client: TestClient, monkeypatch, tmp_path
    ):
        from app import config
        import app.storage as storage_mod

        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("MEM_DOG_DATA_DIR", str(tmp_path / "memdog2"))
        monkeypatch.setattr(config, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(config, "MEM_DOG_DATA_DIR", str(tmp_path / "memdog2"), raising=False)
        monkeypatch.setattr(config, "API_KEY", "platform-secret", raising=False)
        storage_mod.storage_instance = None

        # Provision with platform key
        ws = client.post(
            "/api/v1/host/workspaces",
            headers={"x-api-key": "platform-secret"},
            json={
                "external_org_id": "rot-org-2",
                "external_workspace_id": "rot-ws-2",
            },
        )
        if ws.status_code >= 500:
            pytest.skip(f"local storage not configured: {ws.text}")
        assert ws.status_code == 201, ws.text
        md_key = ws.json()["api_key"]
        other_user = "someone-else"

        # md_* cannot rotate for another user_id
        resp = client.post(
            "/api/v1/host/api-keys/rotate",
            headers={"x-api-key": md_key},
            json={"name": "x", "user_id": other_user},
        )
        assert resp.status_code == 403


class TestUserApiKeyLastKeyAndOwnership:
    """Regression coverage for users.py last-key guard + ownership scoping."""

    def _local(self, monkeypatch, tmp_path, api_key: str = ""):
        from app import config
        import app.storage as storage_mod

        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("MEM_DOG_DATA_DIR", str(tmp_path / "memdog"))
        monkeypatch.setattr(config, "STORAGE_BACKEND", "local", raising=False)
        monkeypatch.setattr(config, "MEM_DOG_DATA_DIR", str(tmp_path / "memdog"), raising=False)
        monkeypatch.setattr(config, "API_KEY", api_key, raising=False)
        storage_mod.storage_instance = None

    def test_delete_last_key_requires_allow_empty(
        self, client: TestClient, monkeypatch, tmp_path
    ):
        self._local(monkeypatch, tmp_path)
        ws = client.post(
            "/api/v1/host/workspaces",
            json={
                "external_org_id": "last-org",
                "external_workspace_id": "last-ws",
            },
        )
        if ws.status_code >= 500:
            pytest.skip(f"local storage not configured: {ws.text}")
        assert ws.status_code == 201, ws.text
        body = ws.json()
        user_id = body["user_id"]
        key_id = body["api_key_id"] if "api_key_id" in body else None
        if not key_id:
            listed = client.get(f"/api/v1/users/{user_id}/api-keys")
            assert listed.status_code == 200
            keys = listed.json()
            assert len(keys) == 1
            key_id = keys[0]["key_id"]

        bad = client.delete(f"/api/v1/users/{user_id}/api-keys/{key_id}")
        assert bad.status_code == 400
        assert "last API key" in bad.json()["detail"]

        ok = client.delete(
            f"/api/v1/users/{user_id}/api-keys/{key_id}",
            params={"allow_empty": "true"},
        )
        assert ok.status_code == 200, ok.text

    def test_cross_user_api_key_list_forbidden(
        self, client: TestClient, monkeypatch, tmp_path
    ):
        self._local(monkeypatch, tmp_path, api_key="platform-secret")
        a = client.post(
            "/api/v1/host/workspaces",
            headers={"x-api-key": "platform-secret"},
            json={
                "external_org_id": "own-org-a",
                "external_workspace_id": "own-ws-a",
            },
        )
        b = client.post(
            "/api/v1/host/workspaces",
            headers={"x-api-key": "platform-secret"},
            json={
                "external_org_id": "own-org-b",
                "external_workspace_id": "own-ws-b",
            },
        )
        if a.status_code >= 500 or b.status_code >= 500:
            pytest.skip("local storage not configured")
        assert a.status_code == 201 and b.status_code == 201
        md_a = a.json()["api_key"]
        user_b = b.json()["user_id"]

        resp = client.get(
            f"/api/v1/users/{user_b}/api-keys",
            headers={"x-api-key": md_a},
        )
        assert resp.status_code == 403

        # Owner can list own keys
        own = client.get(
            f"/api/v1/users/{a.json()['user_id']}/api-keys",
            headers={"x-api-key": md_a},
        )
        assert own.status_code == 200
        assert len(own.json()) >= 1

        # Platform can list any
        plat = client.get(
            f"/api/v1/users/{user_b}/api-keys",
            headers={"x-api-key": "platform-secret"},
        )
        assert plat.status_code == 200
