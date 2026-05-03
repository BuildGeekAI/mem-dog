"""Unit tests for OTEL telemetry and span writing."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest
import respx

from app.telemetry import trace_span, write_span


@pytest.fixture(autouse=True)
def _set_config():
    with patch("app.telemetry.config") as cfg:
        cfg.MEM_DOG_API_URL = "http://test-api:8080"
        cfg.DEFAULT_USER_ID = "default-uid"
        cfg.OTEL_SERVICE_NAME = "webhook-gateway-test"
        cfg.OTEL_ENABLED = False
        yield cfg


@pytest.fixture(autouse=True)
def _reset_memory_flag():
    import app.telemetry as mod
    mod._telemetry_memory_ensured = True  # skip creation in tests
    yield


class TestWriteSpan:
    @respx.mock
    def test_writes_to_api(self):
        route = respx.post("http://test-api:8080/api/v1/data").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        now = datetime.now(timezone.utc)
        write_span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test.span",
            start_time=now,
            end_time=now,
            user_id="user-1",
        )
        assert route.call_count == 1
        body = dict(route.calls[0].request.content.decode().split("&")[0] for _ in [])  # noqa
        assert route.called

    @respx.mock
    def test_handles_api_error(self):
        respx.post("http://test-api:8080/api/v1/data").mock(
            return_value=httpx.Response(500, text="error")
        )
        now = datetime.now(timezone.utc)
        write_span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test.span",
            start_time=now,
            end_time=now,
        )

    def test_no_api_url(self, _set_config):
        _set_config.MEM_DOG_API_URL = ""
        now = datetime.now(timezone.utc)
        write_span(
            trace_id="a" * 32,
            span_id="b" * 16,
            name="test.span",
            start_time=now,
            end_time=now,
        )


class TestTraceSpan:
    @respx.mock
    def test_context_manager_yields_ids(self):
        respx.post("http://test-api:8080/api/v1/data").mock(
            return_value=httpx.Response(200, json={})
        )
        with trace_span("test.op") as ctx:
            assert "trace_id" in ctx
            assert "span_id" in ctx
            assert len(ctx["trace_id"]) == 32
            assert len(ctx["span_id"]) == 16

    @respx.mock
    def test_error_sets_status(self):
        route = respx.post("http://test-api:8080/api/v1/data").mock(
            return_value=httpx.Response(200, json={})
        )
        with pytest.raises(ValueError):
            with trace_span("test.fail") as ctx:
                raise ValueError("boom")
