"""OpenTelemetry instrumentation for model management operations.

Writes OTel-compatible spans to the ``tracing-model-ops`` memory (type
``tracing``, owner ``00000000-0000-0000-0000-000000000001``) so model activation and inference requests
are traceable in the Telemetry UI tab alongside webhook pipeline spans.

Also emits OTel tracer spans (for OTLP backend export) and metrics:

Metrics
-------
  model.activations.total     Counter   tier, model_id
  model.inference.requests    Counter   tier
  model.inference.latency_ms  Histogram tier
  model.inference.tokens      Counter   tier, token_type (prompt|completion)

Span names
----------
  model.activate
  model.inference.chat

All writes to the memory layer are best-effort — exceptions are swallowed so
telemetry never blocks or breaks the main operation path.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.telemetry import get_tracer, get_meter

logger = logging.getLogger("mem_dog.model_telemetry")

# ---------------------------------------------------------------------------
# OTel tracer + meter
# ---------------------------------------------------------------------------

_tracer = get_tracer("mem_dog.model_ops")
_meter  = get_meter("mem_dog.model_ops")

# Metrics
_activations_total   = _meter.create_counter("model.activations.total",   unit="1", description="Model activation requests")
_inference_requests  = _meter.create_counter("model.inference.requests",  unit="1", description="Model inference (chat) requests")
_inference_tokens    = _meter.create_counter("model.inference.tokens",    unit="1", description="Tokens consumed by model inference")
_inference_latency   = _meter.create_histogram("model.inference.latency_ms", unit="ms", description="End-to-end latency of model inference requests")
_embedding_requests  = _meter.create_counter("model.embedding.requests",  unit="1", description="Embedding generation requests")
_embedding_tokens    = _meter.create_counter("model.embedding.tokens",    unit="1", description="Tokens consumed by embedding generation")
_embedding_latency   = _meter.create_histogram("model.embedding.latency_ms", unit="ms", description="End-to-end latency of embedding requests")

# ---------------------------------------------------------------------------
# Memory layer span writer
# ---------------------------------------------------------------------------

_TELEMETRY_MEMORY_ID  = "tracing-model-ops"
_TELEMETRY_USER_ID    = "00000000-0000-0000-0000-000000000001"
_PIPELINE_LABEL       = "model-ops: activate → inference"

# Process-level flag so we only create/check the memory once per process.
_memory_ensured: bool = False


def _ensure_telemetry_memory() -> None:
    """No-op — model telemetry memory disabled."""
    return


def _write_span(**kwargs: Any) -> None:
    """No-op — model telemetry spans disabled to reduce storage noise."""
    return


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def new_trace_id() -> str:
    """128-bit hex trace ID."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:0] or uuid.uuid4().hex


def new_span_id() -> str:
    """64-bit hex span ID."""
    return uuid.uuid4().hex[:16]


# ---------------------------------------------------------------------------
# High-level event recorders
# ---------------------------------------------------------------------------


def record_activation(
    model_id: str,
    tier: str,
    deployment_mode: str,
    status_code: str = "OK",
    error: Optional[str] = None,
) -> str:
    """Emit a ``model.activate`` span; return the trace_id."""
    trace_id = new_trace_id()
    span_id  = new_span_id()
    now      = datetime.now(timezone.utc)

    with _tracer.start_as_current_span("model.activate") as otel_span:
        otel_span.set_attribute("model.id",              model_id)
        otel_span.set_attribute("model.tier",            tier)
        otel_span.set_attribute("model.deployment_mode", deployment_mode)
        if error:
            otel_span.set_attribute("model.error", error[:200])

    attrs: dict[str, Any] = {
        "model_id":        model_id,
        "tier":            tier,
        "deployment_mode": deployment_mode,
    }
    if error:
        attrs["error"] = error[:500]

    _write_span(
        trace_id=trace_id,
        span_id=span_id,
        name="model.activate",
        stage="activation",
        status_code=status_code,
        status_message=error[:200] if error else "",
        kind="INTERNAL",
        start_time=now,
        end_time=now,
        attributes=attrs,
        events=[{"name": "activation_triggered", "timestamp": now.isoformat()}],
    )

    _activations_total.add(1, {"tier": tier, "model_id": model_id or "unknown"})

    return trace_id


def record_inference(
    tier: str,
    model_label: str,
    latency_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    status_code: str = "OK",
    error: Optional[str] = None,
) -> None:
    """Emit a ``model.inference.chat`` span and update metrics."""
    trace_id = new_trace_id()
    span_id  = new_span_id()
    now      = datetime.now(timezone.utc)

    with _tracer.start_as_current_span("model.inference.chat") as otel_span:
        otel_span.set_attribute("model.tier",              tier)
        otel_span.set_attribute("model.label",             model_label)
        otel_span.set_attribute("model.latency_ms",        latency_ms)
        otel_span.set_attribute("model.prompt_tokens",     prompt_tokens)
        otel_span.set_attribute("model.completion_tokens", completion_tokens)
        if error:
            otel_span.set_attribute("model.error", error[:200])

    attrs: dict[str, Any] = {
        "tier":              tier,
        "model":             model_label,
        "latency_ms":        latency_ms,
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if error:
        attrs["error"] = error[:500]

    _write_span(
        trace_id=trace_id,
        span_id=span_id,
        name="model.inference.chat",
        stage="inference",
        status_code=status_code,
        status_message=error[:200] if error else "",
        kind="SERVER",
        start_time=now,
        end_time=now,
        attributes=attrs,
    )

    _inference_requests.add(1, {"tier": tier})
    _inference_latency.record(latency_ms, {"tier": tier})
    if prompt_tokens:
        _inference_tokens.add(prompt_tokens,     {"tier": tier, "token_type": "prompt"})
    if completion_tokens:
        _inference_tokens.add(completion_tokens, {"tier": tier, "token_type": "completion"})


# ---------------------------------------------------------------------------
# Ollama / machine telemetry
# ---------------------------------------------------------------------------

def record_pull(
    machine_id: str,
    model_name: str,
    status: str,
    duration_s: Optional[float] = None,
    error: Optional[str] = None,
) -> None:
    """Emit a span for Ollama model pull (download from registry)."""
    trace_id = new_trace_id()
    span_id = new_span_id()
    now = datetime.now(timezone.utc)

    attrs: dict[str, Any] = {
        "machine_id": machine_id,
        "model": model_name,
        "status": status,
    }
    if duration_s is not None:
        attrs["duration_s"] = round(duration_s, 1)
    if error:
        attrs["error"] = error[:500]

    _write_span(
        trace_id=trace_id,
        span_id=span_id,
        name="model.ollama.pull",
        stage="pull",
        status_code="OK" if status == "complete" else ("ERROR" if status == "error" else "OK"),
        status_message=error[:200] if error else "",
        kind="INTERNAL",
        start_time=now,
        end_time=now,
        attributes=attrs,
    )


def record_copy_from_bucket(
    machine_id: str,
    gcs_filename: str,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Emit a span for copy-from-bucket (tier only)."""
    trace_id = new_trace_id()
    span_id = new_span_id()
    now = datetime.now(timezone.utc)

    attrs: dict[str, Any] = {
        "machine_id": machine_id,
        "gcs_filename": gcs_filename,
        "status": status,
    }
    if error:
        attrs["error"] = error[:500]

    _write_span(
        trace_id=trace_id,
        span_id=span_id,
        name="model.ollama.copy_from_bucket",
        stage="copy",
        status_code="OK" if status == "complete" else "ERROR",
        status_message=error[:200] if error else "",
        kind="INTERNAL",
        start_time=now,
        end_time=now,
        attributes=attrs,
    )


def record_unload(machine_id: str, model_name: str, status: str = "OK") -> None:
    """Emit a span for Ollama model unload."""
    trace_id = new_trace_id()
    span_id = new_span_id()
    now = datetime.now(timezone.utc)

    _write_span(
        trace_id=trace_id,
        span_id=span_id,
        name="model.ollama.unload",
        stage="unload",
        status_code=status,
        kind="INTERNAL",
        start_time=now,
        end_time=now,
        attributes={"machine_id": machine_id, "model": model_name},
    )


def record_machine_chat(
    machine_id: str,
    model: str,
    latency_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    status_code: str = "OK",
    error: Optional[str] = None,
) -> None:
    """Emit a span for chat with category=machine (Ollama)."""
    trace_id = new_trace_id()
    span_id = new_span_id()
    now = datetime.now(timezone.utc)

    attrs: dict[str, Any] = {
        "machine_id": machine_id,
        "model": model,
        "latency_ms": latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if error:
        attrs["error"] = error[:500]

    _write_span(
        trace_id=trace_id,
        span_id=span_id,
        name="model.inference.chat",
        stage="inference",
        status_code=status_code,
        status_message=error[:200] if error else "",
        kind="SERVER",
        start_time=now,
        end_time=now,
        attributes=attrs,
    )

    _inference_requests.add(1, {"tier": f"machine:{machine_id}"})
    _inference_latency.record(latency_ms, {"tier": f"machine:{machine_id}"})
    if prompt_tokens:
        _inference_tokens.add(prompt_tokens,     {"tier": f"machine:{machine_id}", "token_type": "prompt"})
    if completion_tokens:
        _inference_tokens.add(completion_tokens, {"tier": f"machine:{machine_id}", "token_type": "completion"})


# ---------------------------------------------------------------------------
# Embedding telemetry
# ---------------------------------------------------------------------------


def record_embedding(
    engine: str,
    model: str,
    chunks: int,
    dimensions: int,
    latency_ms: int,
    total_tokens: int = 0,
    status_code: str = "OK",
    error: Optional[str] = None,
) -> None:
    """Emit a ``model.embedding`` span and update metrics."""
    trace_id = new_trace_id()
    span_id = new_span_id()
    now = datetime.now(timezone.utc)

    with _tracer.start_as_current_span("model.embedding") as otel_span:
        otel_span.set_attribute("model.engine", engine)
        otel_span.set_attribute("model.label", model)
        otel_span.set_attribute("model.chunks", chunks)
        otel_span.set_attribute("model.dimensions", dimensions)
        otel_span.set_attribute("model.latency_ms", latency_ms)
        otel_span.set_attribute("model.total_tokens", total_tokens)
        if error:
            otel_span.set_attribute("model.error", error[:200])

    attrs: dict[str, Any] = {
        "engine": engine,
        "model": model,
        "chunks": chunks,
        "dimensions": dimensions,
        "latency_ms": latency_ms,
        "total_tokens": total_tokens,
    }
    if error:
        attrs["error"] = error[:500]

    _write_span(
        trace_id=trace_id,
        span_id=span_id,
        name="model.embedding",
        stage="embedding",
        status_code=status_code,
        status_message=error[:200] if error else "",
        kind="SERVER",
        start_time=now,
        end_time=now,
        attributes=attrs,
    )

    _embedding_requests.add(1, {"engine": engine, "model": model})
    _embedding_latency.record(latency_ms, {"engine": engine, "model": model})
    if total_tokens:
        _embedding_tokens.add(total_tokens, {"engine": engine, "model": model})
