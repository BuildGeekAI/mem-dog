"""Per-step processing telemetry for the API layer.

Provides a context manager ``processing_span`` that emits an
OpenTelemetry-compatible ``TelemetrySpan`` into the caller's trace
memory via ``storage.add_data_to_memory``.  The trace memory must be
created by the originating service and passed in as
``telemetry_memory_id``; this module never creates tracing memories.

Usage::

    from app.processing_telemetry import processing_span

    with processing_span(storage, user_id="alice", name="webhook.download", trace_id=trace_id) as span_ctx:
        # ... do work ...
        pass
    # Span is written automatically on exit (success or error).

The function is best-effort — exceptions inside the context manager are
propagated normally; telemetry write failures are swallowed so they
never interrupt the main processing path.
"""

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from app import config

logger = logging.getLogger("mem_dog.processing_telemetry")


@contextmanager
def processing_span(
    storage,
    *,
    user_id: str,
    name: str,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    service_name: str = "memdog-api",
    service_type: str = "gcp_cloud_run_http",
    kind: str = "INTERNAL",
    attributes: Optional[dict[str, Any]] = None,
    telemetry_memory_id: Optional[str] = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager that writes an OTel-compatible span to a tracing memory.

    Yields a mutable ``span_ctx`` dict the caller can annotate with extra
    ``attributes`` before the span is written on exit.

    Args:
        storage: The ``BaseStorage`` instance.
        user_id: Owner of the tracing memory.
        name: Span name, e.g. ``"api.data.download"``.
        trace_id: 32-char hex trace ID; auto-generated if absent.
        parent_span_id: 16-char hex parent span ID.
        service_name: Human-readable service name.
        service_type: GCP service classification.
        kind: OTel SpanKind (SERVER, CLIENT, INTERNAL, PRODUCER, CONSUMER).
        attributes: Initial span attributes; merged with any added inside the block.
        telemetry_memory_id: Target trace memory ID inherited from upstream.
            If absent, the span write is skipped.
    """
    span_id = uuid.uuid4().hex[:16]
    trace_id = trace_id or (uuid.uuid4().hex + uuid.uuid4().hex[:0]) or uuid.uuid4().hex
    start_time = datetime.now(timezone.utc)

    span_ctx: dict[str, Any] = {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "name": name,
        "kind": kind,
        "service_name": service_name,
        "service_type": service_type,
        "attributes": dict(attributes or {}),
        "status_code": "OK",
        "error": None,
    }

    error: Optional[Exception] = None
    try:
        yield span_ctx
    except Exception as exc:
        span_ctx["status_code"] = "ERROR"
        span_ctx["error"] = str(exc)
        error = exc
    finally:
        end_time = datetime.now(timezone.utc)
        duration_ms = (end_time - start_time).total_seconds() * 1000

        span_doc: dict[str, Any] = {
            "trace_id": trace_id,
            "span_id": span_id,
            "name": name,
            "kind": kind,
            "service_name": service_name,
            "service_type": service_type,
            "status": {
                "code": span_ctx["status_code"],
                "message": span_ctx.get("error") or "",
            },
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": round(duration_ms, 3),
            "attributes": span_ctx["attributes"],
        }
        if parent_span_id:
            span_doc["parent_span_id"] = parent_span_id

        _write_span(
            storage=storage,
            span_doc=span_doc,
            user_id=user_id,
            telemetry_memory_id=telemetry_memory_id,
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            status_code=span_ctx["status_code"],
        )

    if error is not None:
        raise error


def _write_span(
    storage,
    span_doc: dict[str, Any],
    user_id: str,
    telemetry_memory_id: Optional[str],
    trace_id: str,
    span_id: str,
    name: str,
    status_code: str,
) -> None:
    """Best-effort: write span JSON to the inherited trace memory.

    Skipped when no *telemetry_memory_id* is provided or memories are disabled.
    """
    if not config.is_memories_enabled() or not telemetry_memory_id:
        return
    try:
        tags = [
            f"trace_id:{trace_id}",
            f"span_id:{span_id}",
            f"service:{span_doc['service_name']}",
            f"status:{status_code}",
            "source:processing_telemetry",
        ]

        storage.create_data(
            content=json.dumps(span_doc, default=str).encode("utf-8"),
            content_type="application/json",
            user=user_id,
            memory_ids=[telemetry_memory_id],
            exclusive_memory_ids=True,
            tags=tags,
            name=f"{name} | {status_code}",
            description=f"[{span_doc['service_name']}] {name} — {status_code}",
            purpose="trace_stage",
        )
    except Exception as exc:
        logger.warning("Failed to write processing span (%s): %s", name, exc)
