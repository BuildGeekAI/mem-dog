"""GKE webhook receiver — Flask app that normalizes payloads and publishes
to an in-cluster NATS server.

Self-contained: does not import from ``main.py`` (which requires
``functions_framework`` and ``google-cloud-pubsub``).

Telemetry
---------
When ``MEM_DOG_API_URL`` is configured the receiver creates a per-request
*tracing* memory (if one isn't already provided) and writes a ``webhook.receiver``
OTel span.  The ``trace_memory_id`` is propagated downstream via NATS headers
so the pull-worker and agent can write their own spans to the same memory.
"""

import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone

import nats as nats_client
import requests as http_requests
from flask import Flask, jsonify, request

logger = logging.getLogger("mem_dog.webhook.receiver.gke")

app = Flask(__name__)

NATS_URL = os.environ.get("NATS_URL", "nats://nats.webhook-pipeline.svc.cluster.local:4222")
NATS_SUBJECT = os.environ.get("NATS_SUBJECT", "webhook.inbound")
MAX_PAYLOAD_BYTES = int(os.environ.get("MAX_PAYLOAD_BYTES", 1_048_576))
MEM_DOG_API_URL = os.environ.get("MEM_DOG_API_URL", "").rstrip("/")
MEM_DOG_API_KEY = os.environ.get("MEM_DOG_API_KEY", "")
_DEFAULT_USER_UUID = "00000000-0000-0000-0000-000000000001"
_TELEMETRY_TIMEOUT = 8

_KNOWN_META_KEYS = frozenset({
    "data_id", "memory", "memory_list", "trace_memory_id", "__trace_context__",
    "owner", "channel_message", "source", "envelope", "envelope_id",
    "source_type", "user_id", "mimetype",
    "url", "download_url", "mime_type", "is_downloaded",
    "gcs_uri",
    # Nested group keys
    "identity", "content", "access", "tracing", "routing",
    # Additional flat keys
    "session_id", "version", "version_label", "prompt", "crawl",
    # Dead fields (still recognized for splitting, dropped by normalization)
    "user_name", "name", "description", "tags", "subject",
    "llm_classification", "participants",
    "timestamp", "services", "device",
})

_FLAT_TO_GROUP: dict[str, tuple[str, str]] = {
    "user_id": ("identity", "user_id"),
    "owner": ("identity", "owner"),
    "mime_type": ("content", "mime_type"),
    "mimetype": ("content", "mime_type"),
    "source_type": ("content", "source_type"),
    "channel_message": ("content", "channel_message"),
    "data_id": ("access", "data_id"),
    "url": ("access", "url"),
    "download_url": ("access", "download_url"),
    "gcs_uri": ("access", "gcs_uri"),
    "is_downloaded": ("access", "is_downloaded"),
    "trace_memory_id": ("tracing", "trace_memory_id"),
    "memory": ("tracing", "memory"),
    "session_id": ("tracing", "session_id"),
    "version": ("tracing", "version"),
    "version_label": ("tracing", "version_label"),
    "prompt": ("routing", "prompt"),
    "crawl": ("routing", "crawl"),
}

_REMOVED_FIELDS = frozenset({
    "user_name", "name", "description", "tags", "subject",
    "llm_classification", "participants", "envelope_id",
    "timestamp", "services", "device",
})

_META_GROUPS = ("identity", "content", "access", "tracing", "routing")


def _nest_meta(meta: dict) -> dict:
    """Migrate flat meta_data to nested group structure (inline version)."""
    result: dict = {}
    for grp in _META_GROUPS:
        if grp in meta and isinstance(meta[grp], dict):
            result[grp] = dict(meta[grp])
    if "__trace_context__" in meta:
        result["__trace_context__"] = meta["__trace_context__"]
    for key, value in meta.items():
        if key in _META_GROUPS or key == "__trace_context__":
            continue
        if key in _REMOVED_FIELDS:
            continue
        mapping = _FLAT_TO_GROUP.get(key)
        if mapping is None:
            result[key] = value
            continue
        group, target_key = mapping
        result.setdefault(group, {})
        if key == "memory_list":
            if "memory" not in result[group]:
                result[group]["memory"] = {"other": value} if isinstance(value, list) else value
            continue
        if key == "mimetype":
            if "mime_type" not in result[group]:
                result[group]["mime_type"] = value
            continue
        if target_key not in result[group]:
            result[group][target_key] = value
    return result

_loop = None
_loop_thread = None
_nc = None


def _generate_trace_id() -> str:
    return uuid.uuid4().hex


def _generate_span_id() -> str:
    return uuid.uuid4().hex[:16]


# ---------------------------------------------------------------------------
# Telemetry helpers — best-effort, never block the main path
# ---------------------------------------------------------------------------

def _api_headers() -> dict:
    h = {"Content-Type": "application/json"}
    if MEM_DOG_API_KEY:
        h["x-api-key"] = MEM_DOG_API_KEY
    return h


def _create_tracing_memory(user_id: str) -> str | None:
    """Create a per-request tracing memory and return its memory_id."""
    if not MEM_DOG_API_URL:
        return None
    try:
        resp = http_requests.post(
            f"{MEM_DOG_API_URL}/api/v1/memories",
            json={
                "memory_type": "tracing",
                "name": "Webhook trace",
                "description": "Per-request trace container for OTel spans",
                "user_id": user_id,
                "metadata": {"source": "webhook_receiver_gke", "auto_created": True},
            },
            headers=_api_headers(),
            timeout=_TELEMETRY_TIMEOUT,
        )
        resp.raise_for_status()
        mid = resp.json().get("memory_id", "")
        if mid:
            logger.info("Created tracing memory: %s", mid)
        return mid or None
    except Exception as exc:
        logger.warning("Could not create tracing memory: %s", exc)
        return None


def _write_receiver_span(
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    trace_memory_id: str,
    start_time: datetime,
    end_time: datetime,
    status_code: str,
    user_id: str,
    payload_size: int,
) -> None:
    """Write a receiver OTel span to the tracing memory."""
    if not MEM_DOG_API_URL or not trace_memory_id:
        return
    duration_ms = (end_time - start_time).total_seconds() * 1000
    span = {
        "trace_id": trace_id,
        "span_id": span_id,
        "name": "webhook.receiver",
        "kind": "SERVER",
        "service_name": "webhook-receiver-gke",
        "service_type": "gke_deployment",
        "status": {"code": status_code, "message": ""},
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_ms": round(duration_ms, 3),
        "attributes": {"payload_size": payload_size},
    }
    if parent_span_id:
        span["parent_span_id"] = parent_span_id
    tags = [
        f"trace_id:{trace_id}",
        f"span_id:{span_id}",
        "stage:receiver",
        "service:webhook-receiver-gke",
        f"status:{status_code}",
        "kind:SERVER",
        "source:webhook_telemetry",
    ]
    if parent_span_id:
        tags.append(f"parent_span_id:{parent_span_id}")
    try:
        http_requests.post(
            f"{MEM_DOG_API_URL}/api/v1/data",
            data={
                "content": json.dumps(span, default=str),
                "name": f"webhook.receiver | {status_code}",
                "description": f"[webhook-receiver-gke] webhook.receiver — SERVER span — {status_code}",
                "tags": ",".join(tags),
                "memory_ids": trace_memory_id,
                "exclusive": "true",
                "owner_user_id": user_id,
            },
            headers={"x-api-key": MEM_DOG_API_KEY} if MEM_DOG_API_KEY else {},
            timeout=_TELEMETRY_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("Failed to write receiver span: %s", exc)


def _normalize_payload(payload: dict) -> tuple[dict, dict]:
    """Lightweight normalization: split into (data, meta_data)."""
    has_data = "data" in payload and isinstance(payload.get("data"), dict)
    meta_bucket = None
    if has_data:
        if "meta_data" in payload and isinstance(payload.get("meta_data"), dict):
            meta_bucket = dict(payload.get("meta_data") or {})
        elif "telemetry" in payload and isinstance(payload.get("telemetry"), dict):
            meta_bucket = dict(payload.get("telemetry") or {})

    if has_data and meta_bucket is not None:
        data = payload.get("data")
        meta = meta_bucket
        for k in _KNOWN_META_KEYS:
            if k in payload and k not in meta:
                meta[k] = payload[k]
    else:
        meta = {k: payload[k] for k in _KNOWN_META_KEYS if k in payload}
        data = {k: v for k, v in payload.items() if k not in _KNOWN_META_KEYS}

    uid = (
        data.get("user_id") or data.get("userId") or data.get("sender") or
        meta.get("user_id")
    )
    if uid and "user_id" not in meta:
        meta["user_id"] = str(uid)

    # Migrate to nested group structure
    meta = _nest_meta(meta)
    return data, meta


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _loop_thread.start()
    return _loop


async def _get_nats():
    global _nc
    if _nc is None or not _nc.is_connected:
        _nc = await nats_client.connect(NATS_URL)
        logger.info("Connected to NATS at %s", NATS_URL)
    return _nc


def _publish_sync(subject: str, data: bytes, headers: dict) -> None:
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(_publish(subject, data, headers), loop)
    future.result(timeout=10)


async def _publish(subject: str, data: bytes, headers: dict) -> None:
    nc = await _get_nats()
    await nc.publish(subject, data, headers=headers)
    await nc.flush()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/", methods=["POST"])
@app.route("/<path:_>", methods=["POST"])
def receive(_=None):
    """Accept a webhook payload, normalize it, and publish to NATS."""
    content_length = request.content_length or 0
    if content_length > MAX_PAYLOAD_BYTES:
        return jsonify({
            "error": f"Payload too large. Maximum size is {MAX_PAYLOAD_BYTES} bytes."
        }), 413

    raw_body = request.get_data(as_text=True)
    if not raw_body:
        return jsonify({"error": "Request body is empty."}), 400

    span_start = datetime.now(timezone.utc)
    span_id = _generate_span_id()

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Invalid JSON: {exc}"}), 400

    if not isinstance(payload, dict):
        return jsonify({"error": "Payload must be a JSON object."}), 400

    data, meta_data = _normalize_payload(payload)
    payload = {"data": data, "meta_data": meta_data}

    resolved_user_id = (
        (meta_data.get("identity") or {}).get("user_id")
        or meta_data.get("user_id")
        or _DEFAULT_USER_UUID
    )

    # Inherit trace context from upstream (e.g. Webhook Gateway envelope)
    upstream_ctx = meta_data.get("__trace_context__") or {}
    trace_id = upstream_ctx.get("trace_id") or _generate_trace_id()
    parent_span_id = upstream_ctx.get("span_id")

    # Ensure a tracing memory exists for the full pipeline
    trace_memory_id = (
        (meta_data.get("tracing") or {}).get("trace_memory_id")
        or meta_data.get("trace_memory_id")
        or ""
    )
    if not trace_memory_id:
        trace_memory_id = _create_tracing_memory(resolved_user_id) or ""

    received_at = span_start.isoformat()

    message_data = json.dumps(payload).encode("utf-8")
    headers = {
        "X-Trace-Id": trace_id,
        "X-Span-Id": span_id,
        "X-User-Id": str(resolved_user_id),
        "X-Received-At": received_at,
    }
    if trace_memory_id:
        headers["X-Trace-Memory-Id"] = trace_memory_id

    # Write early "PROCESSING" span so tracing is visible immediately
    if trace_memory_id:
        _write_receiver_span(
            trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id,
            trace_memory_id=trace_memory_id, start_time=span_start,
            end_time=datetime.now(timezone.utc), status_code="PROCESSING",
            user_id=resolved_user_id, payload_size=len(raw_body),
        )

    status = "OK"
    try:
        _publish_sync(NATS_SUBJECT, message_data, headers)
    except Exception as exc:
        logger.error("Failed to publish to NATS: %s", exc)
        status = "ERROR"
        _write_receiver_span(
            trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id,
            trace_memory_id=trace_memory_id, start_time=span_start,
            end_time=datetime.now(timezone.utc), status_code=status,
            user_id=resolved_user_id, payload_size=len(raw_body),
        )
        return jsonify({"error": f"Failed to publish: {exc}"}), 500

    span_end = datetime.now(timezone.utc)
    _write_receiver_span(
        trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id,
        trace_memory_id=trace_memory_id, start_time=span_start,
        end_time=span_end, status_code=status,
        user_id=resolved_user_id, payload_size=len(raw_body),
    )

    logger.info(
        "Webhook published to NATS | subject=%s trace=%s trace_mem=%s size=%d",
        NATS_SUBJECT, trace_id[:8], trace_memory_id[:12] if trace_memory_id else "-",
        len(message_data),
    )

    return jsonify({
        "status": "accepted",
        "received_at": received_at,
        "trace_id": trace_id,
        "trace_memory_id": trace_memory_id or None,
    }), 202


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
