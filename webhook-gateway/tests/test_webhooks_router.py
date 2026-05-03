"""Integration tests for the webhooks router.

Uses the ASGI test client so the full request path is exercised:
receive -> adapter -> identity -> (optional LLM) -> envelope -> forward.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.forwarder import ForwardResult


@pytest.fixture(autouse=True)
def _mock_forward():
    """Mock the forwarder so tests don't make real HTTP calls."""
    result = ForwardResult(success=True, status_code=202, message_id="msg-test", trace_id="tid-test")
    with patch("app.routers.webhooks.forward_envelope", new_callable=AsyncMock, return_value=result):
        yield


@pytest.fixture(autouse=True)
def _mock_identity():
    """Mock identity resolution to return a deterministic user_id."""
    with patch("app.routers.webhooks.resolve_user_id", new_callable=AsyncMock, return_value="user-resolved"):
        yield


@pytest.fixture(autouse=True)
def _mock_llm():
    """Mock LLM calls."""
    with patch("app.routers.webhooks.classify_message", new_callable=AsyncMock, return_value={"intent": "informational"}), \
         patch("app.routers.webhooks.summarize_context", new_callable=AsyncMock, return_value="Summary."):
        yield


@pytest.fixture(autouse=True)
def _mock_telemetry():
    """Disable telemetry span writes in tests."""
    with patch("app.routers.webhooks.trace_span") as mock_ts:
        from contextlib import contextmanager

        @contextmanager
        def _fake_span(*a, **kw):
            yield {"trace_id": "a" * 32, "span_id": "b" * 16}

        mock_ts.side_effect = _fake_span
        yield


class TestGenericWebhook:
    def test_accepts_json_payload(self, client):
        resp = client.post("/webhooks/generic", json={"text": "hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["channel_type"] == "generic"
        assert "trace_id" in body

    def test_rejects_empty_body(self, client):
        resp = client.post("/webhooks/generic", content=b"")
        assert resp.status_code == 400

    def test_rejects_invalid_json(self, client):
        resp = client.post(
            "/webhooks/generic",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_rejects_non_object(self, client):
        resp = client.post("/webhooks/generic", json=[1, 2, 3])
        assert resp.status_code == 400


class TestEmailWebhook:
    def test_sendgrid_payload(self, client):
        payload = {
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Test",
            "text": "Body text",
        }
        resp = client.post("/webhooks/email", json=payload)
        assert resp.status_code == 200
        assert resp.json()["channel_type"] == "email"


class TestVideoWebhook:
    def test_zoom_payload(self, client):
        payload = {
            "event": "meeting.ended",
            "payload": {
                "object": {
                    "id": 123,
                    "uuid": "z-uuid",
                    "host_id": "host-1",
                    "topic": "Standup",
                },
            },
        }
        resp = client.post("/webhooks/video", json=payload)
        assert resp.status_code == 200
        assert resp.json()["channel_type"] == "video"


class TestUnsupportedChannel:
    def test_returns_400(self, client):
        resp = client.post("/webhooks/nonexistent_channel", json={"text": "hello"})
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["service"] == "webhook-gateway"
