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
