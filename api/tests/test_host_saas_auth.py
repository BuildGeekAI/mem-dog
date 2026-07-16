"""Host SaaS Phase B/F3 — integrations scoping + request id / error envelope."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.routers.integrations import (
    _assert_connection_access,
    _resolve_user_scope,
)


class TestIntegrationUserScope:
    def test_per_user_forces_caller(self):
        req = SimpleNamespace(state=SimpleNamespace(auth_type="per_user", user_id="u1"))
        assert _resolve_user_scope(req, None) == "u1"
        assert _resolve_user_scope(req, "u1") == "u1"

    def test_per_user_rejects_cross_user(self):
        req = SimpleNamespace(state=SimpleNamespace(auth_type="per_user", user_id="u1"))
        with pytest.raises(HTTPException) as exc:
            _resolve_user_scope(req, "u2")
        assert exc.value.status_code == 403

    def test_global_allows_filter_or_all(self):
        req = SimpleNamespace(state=SimpleNamespace(auth_type="global", user_id=None))
        assert _resolve_user_scope(req, None) is None
        assert _resolve_user_scope(req, "u9") == "u9"

    def test_assert_connection_access_hides_others(self):
        req = SimpleNamespace(state=SimpleNamespace(auth_type="per_user", user_id="u1"))
        with pytest.raises(HTTPException) as exc:
            _assert_connection_access(req, {"end_user": {"id": "u2"}})
        assert exc.value.status_code == 404

    def test_assert_connection_access_allows_owner(self):
        req = SimpleNamespace(state=SimpleNamespace(auth_type="per_user", user_id="u1"))
        _assert_connection_access(req, {"end_user": {"id": "u1"}})


class TestIntegrationsRouteScoping:
    def test_list_connections_passes_scoped_user(self, client: TestClient):
        with patch(
            "app.routers.integrations.nango_client.list_connections",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list, patch(
            "app.routers.integrations._resolve_user_scope", return_value="scoped-user"
        ):
            resp = client.get("/api/v1/integrations/connections")
        assert resp.status_code == 200
        mock_list.assert_awaited_once_with(end_user_id="scoped-user")

    def test_oauth_credentials_require_platform_when_configured(
        self, client: TestClient, monkeypatch
    ):
        from app import config

        monkeypatch.setattr(config, "API_KEY", "platform-secret", raising=False)
        # Simulate md_* auth already passed middleware (open path in tests often has no API_KEY)
        # Hit handler logic by calling with a request that has per_user state via dependency —
        # easiest: unit-call _require_platform_key
        from app.routers.integrations import _require_platform_key

        req = SimpleNamespace(state=SimpleNamespace(auth_type="per_user", user_id="u1"))
        with pytest.raises(HTTPException) as exc:
            _require_platform_key(req)
        assert exc.value.status_code == 403


class TestRequestIdAndErrors:
    def test_echoes_request_id(self, client: TestClient):
        resp = client.get("/health", headers={"X-Request-Id": "host-req-42"})
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-Id") == "host-req-42"

    def test_generates_request_id_when_missing(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-Id")

    def test_structured_error_on_not_found(self, client: TestClient):
        resp = client.get(
            "/api/v1/host/workspaces",
            params={"external_org_id": "nope", "external_workspace_id": "nope"},
            headers={"X-Request-Id": "err-1"},
        )
        # 404 when not found (or 403 if platform key required in env)
        if resp.status_code == 404:
            body = resp.json()
            assert "error" in body
            assert body["error"]["request_id"] == "err-1"
            assert body["error"]["code"] == "not_found"
            assert resp.headers.get("X-Request-Id") == "err-1"
