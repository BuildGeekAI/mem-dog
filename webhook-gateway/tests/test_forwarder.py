"""Unit tests for the webhook forwarder."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from app.forwarder import forward_envelope


@pytest.fixture(autouse=True)
def _set_config():
    with patch("app.forwarder.config") as cfg:
        cfg.WEBHOOK_GATEWAY_URL = "http://test-gw/webhook"
        cfg.WEBHOOK_API_KEY = "test-key"
        yield cfg


@pytest.fixture()
def envelope():
    return {
        "data": {"text": "hello"},
        "meta_data": {
            "content": {"source_type": "email"},
        },
    }


class TestForwardEnvelope:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success(self, envelope):
        respx.post("http://test-gw/webhook").mock(
            return_value=httpx.Response(
                202,
                json={"status": "accepted", "message_id": "msg-1", "trace_id": "tid"},
            )
        )
        result = await forward_envelope(envelope)
        assert result.success is True
        assert result.status_code == 202
        assert result.message_id == "msg-1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_client_error_no_retry(self, envelope):
        respx.post("http://test-gw/webhook").mock(
            return_value=httpx.Response(400, text="bad request")
        )
        result = await forward_envelope(envelope)
        assert result.success is False
        assert result.status_code == 400

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_error_retries(self, envelope):
        route = respx.post("http://test-gw/webhook")
        route.side_effect = [
            httpx.Response(500, text="internal error"),
            httpx.Response(500, text="internal error"),
            httpx.Response(202, json={"status": "accepted", "message_id": "msg-2"}),
        ]
        with patch("app.forwarder._BASE_DELAY_S", 0.01):
            result = await forward_envelope(envelope)
        assert result.success is True
        assert result.message_id == "msg-2"

    @pytest.mark.asyncio
    async def test_no_url_configured(self, envelope, _set_config):
        _set_config.WEBHOOK_GATEWAY_URL = ""
        result = await forward_envelope(envelope)
        assert result.success is False
        assert "not configured" in result.error

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_api_key_header(self, envelope):
        route = respx.post("http://test-gw/webhook").mock(
            return_value=httpx.Response(202, json={})
        )
        await forward_envelope(envelope)
        assert route.calls[0].request.headers["x-api-key"] == "test-key"
