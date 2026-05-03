"""E2E test for the Webhook Gateway.

Requires a running memdog API + Webhook Gateway stack.
Run with: pytest testing/api/e2e/test_webhook_gateway.py

Marked as integration so it is skipped by default in unit-test runs.
"""

from __future__ import annotations

import os
import time

import pytest
import httpx

GATEWAY_URL = os.getenv("WEBHOOK_GATEWAY_URL", "http://localhost:8070")
API_URL = os.getenv("MEM_DOG_API_URL", "http://localhost:8080")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def gateway_healthy():
    """Skip the entire module if the gateway is not reachable."""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip(f"Gateway not healthy: {resp.status_code}")
    except Exception as exc:
        pytest.skip(f"Gateway not reachable: {exc}")


class TestGenericWebhookE2E:
    def test_forward_and_store(self, gateway_healthy):
        """POST a generic webhook and verify it reaches the API."""
        payload = {
            "text": f"E2E test payload {time.time()}",
            "source_type": "other",
            "user_id": "e2e-test-user",
        }
        resp = httpx.post(f"{GATEWAY_URL}/webhooks/generic", json=payload, timeout=30)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["channel_type"] == "generic"
        assert "trace_id" in body


class TestEmailWebhookE2E:
    def test_sendgrid_email(self, gateway_healthy):
        """POST a SendGrid-style email webhook."""
        payload = {
            "from": "e2e-sender@test.com",
            "to": "e2e-recipient@test.com",
            "subject": f"E2E Test {time.time()}",
            "text": "E2E email body",
        }
        resp = httpx.post(f"{GATEWAY_URL}/webhooks/email", json=payload, timeout=30)
        assert resp.status_code == 200
        assert resp.json()["channel_type"] == "email"


class TestVideoWebhookE2E:
    def test_zoom_webhook(self, gateway_healthy):
        """POST a Zoom-style video conferencing webhook."""
        payload = {
            "event": "meeting.ended",
            "payload": {
                "object": {
                    "id": 99999,
                    "uuid": "e2e-uuid",
                    "host_id": "e2e-host",
                    "topic": "E2E Test Meeting",
                },
            },
        }
        resp = httpx.post(f"{GATEWAY_URL}/webhooks/video", json=payload, timeout=30)
        assert resp.status_code == 200
        assert resp.json()["channel_type"] == "video"


class TestHealthE2E:
    def test_health(self, gateway_healthy):
        resp = httpx.get(f"{GATEWAY_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_ready(self, gateway_healthy):
        resp = httpx.get(f"{GATEWAY_URL}/ready", timeout=10)
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ready", "degraded")
