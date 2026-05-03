"""Shared fixtures for Webhook Gateway tests."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure test-safe defaults before anything imports config
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("WEBHOOK_GATEWAY_URL", "http://test-webhook-gw/webhook")
os.environ.setdefault("WEBHOOK_API_KEY", "test-wh-key")
os.environ.setdefault("MEM_DOG_API_URL", "http://test-api:8080")
os.environ.setdefault("OTEL_ENABLED", "false")

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    """Synchronous ``TestClient`` for router-level tests."""
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture()
async def async_client():
    """Async ``httpx.AsyncClient`` backed by the ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
