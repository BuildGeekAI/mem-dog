"""OTEL tracing for the Webhook Gateway.

Dual-mode telemetry:

1. Standard OTEL SDK export when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.
2. Writes spans as tracing memories to the mem-dog API (same pattern as
   ``webhook/receiver/main.py`` ``_write_telemetry_span``).

Both modes can run simultaneously.  Mode 2 always runs when
``MEM_DOG_API_URL`` is configured so traces are queryable through the
mem-dog telemetry dashboard regardless of collector availability.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

import httpx

from . import config

_log = logging.getLogger("webhook_gateway.telemetry")

_TELEMETRY_TIMEOUT_S = 10
_DEFAULT_TELEMETRY_MEMORY_ID = "telemetry-webhook-gateway"
_telemetry_memory_ensured: bool = False


# ---------------------------------------------------------------------------
# OTEL SDK setup (optional)
# ---------------------------------------------------------------------------

_tracer = None


def setup_otel() -> None:
    """Initialise the OTEL SDK tracer and FastAPI instrumentation.

    Called once at app startup.  No-ops if OTEL is disabled.
    """
    global _tracer
    if not config.OTEL_ENABLED:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        resource = Resource.create({"service.name": config.OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)

        if config.OTEL_EXPORTER_OTLP_ENDPOINT:
            if config.OTEL_EXPORTER_OTLP_PROTOCOL == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )
            else:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
            exporter = OTLPSpanExporter(endpoint=config.OTEL_EXPORTER_OTLP_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        else:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(config.OTEL_SERVICE_NAME)
        _log.info("OTEL SDK initialised (endpoint=%s)", config.OTEL_EXPORTER_OTLP_ENDPOINT or "console")
    except Exception as exc:
        _log.warning("OTEL SDK setup failed: %s", exc)


def get_tracer():
    """Return the global OTEL tracer, or ``None`` if not initialised."""
    return _tracer


# ---------------------------------------------------------------------------
# mem-dog API span writes (always-on when API URL is configured)
# ---------------------------------------------------------------------------

def _api_headers() -> dict[str, str]:
    """Return auth headers for mem-dog API calls."""
    h: dict[str, str] = {}
    if config.MEM_DOG_API_KEY:
        h["x-api-key"] = config.MEM_DOG_API_KEY
    return h


def _ensure_telemetry_memory() -> None:
    """Create the default gateway telemetry memory if it does not exist."""
    global _telemetry_memory_ensured
    if _telemetry_memory_ensured or not config.MEM_DOG_API_URL:
        return

    base = f"{config.MEM_DOG_API_URL}/api/v1/memories"
    headers = _api_headers()
    try:
        resp = httpx.get(
            f"{base}/{_DEFAULT_TELEMETRY_MEMORY_ID}",
            headers=headers,
            timeout=_TELEMETRY_TIMEOUT_S,
        )
        if resp.status_code == 200:
            _telemetry_memory_ensured = True
            return
    except Exception:
        pass

    try:
        resp = httpx.post(
            base,
            json={
                "memory_id": _DEFAULT_TELEMETRY_MEMORY_ID,
                "memory_type": "tracing",
                "name": "Webhook Gateway Telemetry",
                "description": (
                    "OTel-compatible spans for every request processed by "
                    "the Webhook Gateway: receive, classify, normalise, forward."
                ),
                "user_id": config.DEFAULT_USER_ID,
                "metadata": {
                    "source": "webhook_gateway",
                    "otel_compatible": True,
                    "auto_created": True,
                },
            },
            headers=headers,
            timeout=_TELEMETRY_TIMEOUT_S,
        )
        resp.raise_for_status()
        _telemetry_memory_ensured = True
        _log.info("Created telemetry memory: %s", _DEFAULT_TELEMETRY_MEMORY_ID)
    except Exception as exc:
        _log.warning("Could not ensure telemetry memory: %s", exc)


def write_span(
    *,
    trace_id: str,
    span_id: str,
    name: str,
    status_code: str = "OK",
    start_time: datetime,
    end_time: datetime,
    parent_span_id: str | None = None,
    attributes: dict[str, Any] | None = None,
    user_id: str | None = None,
    memory_id: str | None = None,
) -> None:
    """Write a single OTel span to the mem-dog API as a tracing memory entry."""
    if not config.MEM_DOG_API_URL:
        return

    if not memory_id:
        _ensure_telemetry_memory()
        memory_id = _DEFAULT_TELEMETRY_MEMORY_ID

    duration_ms = (end_time - start_time).total_seconds() * 1000

    span: dict[str, Any] = {
        "trace_id": trace_id,
        "span_id": span_id,
        "name": name,
        "kind": "SERVER",
        "service_name": config.OTEL_SERVICE_NAME,
        "service_type": "webhook_gateway",
        "status": {"code": status_code, "message": ""},
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_ms": round(duration_ms, 3),
    }
    if parent_span_id:
        span["parent_span_id"] = parent_span_id
    if attributes:
        span["attributes"] = attributes

    tags = [
        f"trace_id:{trace_id}",
        f"span_id:{span_id}",
        f"service:{config.OTEL_SERVICE_NAME}",
        f"status:{status_code}",
        "source:webhook_gateway_telemetry",
    ]
    if parent_span_id:
        tags.append(f"parent_span_id:{parent_span_id}")

    post_data: dict[str, str] = {
        "content": json.dumps(span, default=str),
        "name": f"{name} | {status_code}",
        "description": f"[{config.OTEL_SERVICE_NAME}] {name} — {status_code}",
        "tags": ",".join(tags),
        "memory_ids": memory_id,
        "exclusive": "true",
        "owner_user_id": user_id or config.DEFAULT_USER_ID,
    }

    try:
        resp = httpx.post(
            f"{config.MEM_DOG_API_URL}/api/v1/data",
            data=post_data,
            headers=_api_headers(),
            timeout=_TELEMETRY_TIMEOUT_S,
        )
        resp.raise_for_status()
    except Exception as exc:
        _log.warning("Failed to write telemetry span (name=%s): %s", name, exc)


# ---------------------------------------------------------------------------
# Convenience context manager
# ---------------------------------------------------------------------------

@contextmanager
def trace_span(
    name: str,
    *,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    attributes: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> Generator[dict[str, str], None, None]:
    """Context manager that times a block and writes a span on exit.

    Yields a dict with ``trace_id`` and ``span_id`` so callers can
    propagate them to child spans.
    """
    tid = trace_id or uuid.uuid4().hex
    sid = uuid.uuid4().hex[:16]
    start = datetime.now(timezone.utc)
    ctx = {"trace_id": tid, "span_id": sid}
    status = "OK"
    try:
        yield ctx
    except Exception:
        status = "ERROR"
        raise
    finally:
        end = datetime.now(timezone.utc)
        write_span(
            trace_id=tid,
            span_id=sid,
            name=name,
            status_code=status,
            start_time=start,
            end_time=end,
            parent_span_id=parent_span_id,
            attributes=attributes,
            user_id=user_id,
        )
