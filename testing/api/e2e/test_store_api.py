"""
E2E tests for /api/v1/store CRUD API.

Uses the real app (no mock storage). Each backend (redis, postgres, supabase, gcs)
is tested only when configured via env vars. Run with:

  SUPABASE_URL='https://xxx.supabase.co' SUPABASE_KEY='...' pytest testing/api/e2e/test_store_api.py -v -k supabase

Requires the store_kv table in Supabase (see docs/architecture/ and storage guides).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../api"))

from fastapi.testclient import TestClient


@pytest.fixture
def store_client():
    """Real app (no mock storage) for store API tests."""
    from main import app
    return TestClient(app)


def _test_store_crud(client: TestClient, backend: str, key_prefix: str = "e2e_"):
    """Run full CRUD cycle for a backend."""
    key = f"{key_prefix}supabase_test"
    value = b"hello from e2e test"
    param = {backend: True}

    # PUT
    r = client.put(f"/api/v1/store/{key}", content=value, params=param)
    assert r.status_code == 200, r.text
    assert r.json().get("backend") == backend

    # GET
    r = client.get(f"/api/v1/store/{key}", params=param)
    assert r.status_code == 200, r.text
    assert r.content == value

    # LIST
    r = client.get("/api/v1/store", params={**param, "prefix": key_prefix})
    assert r.status_code == 200, r.text
    keys = r.json().get("keys", [])
    assert key in keys

    # DELETE
    r = client.delete(f"/api/v1/store/{key}", params=param)
    assert r.status_code == 204

    # GET after delete -> 404
    r = client.get(f"/api/v1/store/{key}", params=param)
    assert r.status_code == 404


class TestStoreApiSupabase:
    """Supabase store E2E tests. Skip when SUPABASE_URL/SUPABASE_KEY not set."""

    @pytest.fixture(autouse=True)
    def _check_supabase(self):
        from app import config
        if not config.is_supabase_store_enabled():
            pytest.skip(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY)."
            )

    def test_supabase_crud(self, store_client):
        """PUT, GET, LIST, DELETE via supabase=true."""
        _test_store_crud(store_client, "supabase")
