"""Host SaaS F2 — ingest rate / body / project storage quotas."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import quotas


class TestQuotaHelpers:
    def setup_method(self):
        quotas.reset_quotas_for_tests()

    def test_body_size_enforced(self, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "QUOTA_MAX_BODY_BYTES", 10, raising=False)
        with pytest.raises(HTTPException) as exc:
            quotas.check_body_size(11)
        assert exc.value.status_code == 429
        assert exc.value.detail["code"] == "quota_exceeded"
        assert exc.value.headers.get("Retry-After")

    def test_body_size_disabled(self, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "QUOTA_MAX_BODY_BYTES", 0, raising=False)
        quotas.check_body_size(10_000_000)

    def test_ingest_rate_limit(self, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "QUOTA_INGEST_RPM", 2, raising=False)
        req = SimpleNamespace(
            url=SimpleNamespace(path="/api/v1/data"),
            method="POST",
            state=SimpleNamespace(user_id="u1"),
            headers={},
            client=SimpleNamespace(host="1.2.3.4"),
        )
        quotas.check_ingest_rate(req)
        quotas.check_ingest_rate(req)
        with pytest.raises(HTTPException) as exc:
            quotas.check_ingest_rate(req)
        assert exc.value.status_code == 429
        assert exc.value.detail["code"] == "rate_limited"

    def test_project_storage_quota(self, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "QUOTA_MAX_STORAGE_BYTES_PER_PROJECT", 100, raising=False)
        storage = MagicMock()
        storage.list_all_metadata_paginated.return_value = (
            [SimpleNamespace(size=80)],
            1,
        )
        with pytest.raises(HTTPException) as exc:
            quotas.check_project_storage(
                storage, user_id="u1", project_id="proj_x", additional_bytes=30
            )
        assert exc.value.detail["code"] == "quota_exceeded"


class TestQuotaAPI:
    def setup_method(self):
        quotas.reset_quotas_for_tests()

    def test_content_length_rejected(self, client: TestClient, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "QUOTA_MAX_BODY_BYTES", 5, raising=False)
        monkeypatch.setattr(config, "API_KEY", "", raising=False)
        resp = client.post(
            "/api/v1/data",
            data={"content": "hello-world", "mime_type": "text/plain"},
            headers={"Content-Length": "100"},
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "quota_exceeded"
        assert resp.headers.get("Retry-After")

    def test_ingest_rpm_via_api(self, client: TestClient, monkeypatch):
        from app import config
        from unittest.mock import patch, MagicMock

        monkeypatch.setattr(config, "QUOTA_INGEST_RPM", 2, raising=False)
        monkeypatch.setattr(config, "QUOTA_MAX_BODY_BYTES", 0, raising=False)
        monkeypatch.setattr(config, "API_KEY", "", raising=False)
        quotas.reset_quotas_for_tests()

        mock_storage = MagicMock()
        mock_storage.create_data.return_value = ("data_x", 1)

        with patch("app.routers.data.get_storage", return_value=mock_storage):
            r1 = client.post(
                "/api/v1/data",
                data={"content": "a", "mime_type": "text/plain"},
            )
            r2 = client.post(
                "/api/v1/data",
                data={"content": "b", "mime_type": "text/plain"},
            )
            r3 = client.post(
                "/api/v1/data",
                data={"content": "c", "mime_type": "text/plain"},
            )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert r3.json()["error"]["code"] == "rate_limited"
        assert r3.headers.get("Retry-After")
