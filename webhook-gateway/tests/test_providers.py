"""Unit tests for the providers router."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


class TestListProviders:
    def test_returns_active_and_catalog(self, client):
        resp = client.get("/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "active" in data
        assert "providers" in data
        assert data["active"]["provider"] is not None
        assert len(data["providers"]) > 10

    def test_active_flag_set(self, client):
        resp = client.get("/providers")
        data = resp.json()
        active_entries = [p for p in data["providers"] if p["active"]]
        assert len(active_entries) == 1


class TestActiveProvider:
    def test_returns_provider_info(self, client):
        resp = client.get("/providers/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "provider" in data
        assert "model" in data
        assert "configured" in data
