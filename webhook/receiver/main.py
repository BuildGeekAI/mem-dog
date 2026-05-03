"""Webhook Receiver Cloud Function.

HTTP-triggered Cloud Function that accepts incoming webhook payloads,
validates them, and publishes them to a Pub/Sub topic for async processing.

For every accepted request this function:
1. Generates a ``trace_id`` (128-bit hex) and ``span_id`` (64-bit hex) that
   form the root of the OTel trace for this webhook invocation.
2. Embeds both IDs in the Pub/Sub message attributes so downstream stages
   can link their own spans to this root span.
3. Writes a best-effort OTel-compatible span to the incoming
   ``trace_memory_id`` (if present in the payload), or to the default
   ``telemetry-webhook-pipeline`` memory otherwise.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import functions_framework
import requests as _requests
from flask import Request, jsonify
from google.cloud import pubsub_v1

logger = logging.getLogger("mem_dog.webhook.receiver")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
PUBSUB_TOPIC = os.environ.get("WEBHOOK_PUBSUB_TOPIC", "memdog-webhook-dev")
MAX_PAYLOAD_BYTES = int(os.environ.get("MAX_PAYLOAD_BYTES", 1_048_576))  # 1 MB

# Base URL of the memdog API used for telemetry span writes.
_MEM_DOG_API_URL: str = os.environ.get("MEM_DOG_API_URL", "").rstrip("/")

# Canonical default user UUID — must match the UUID used by all other services.
# Never read DEFAULT_USER env var here (it may be set to a non-UUID like "demo").
_DEFAULT_USER_UUID = "00000000-0000-0000-0000-000000000001"

_publisher = None

# Canonical message format: known keys go in meta_data; rest in data (matches processor/router).
# Input may use "meta_data" or "telemetry" as the second key; we publish as "meta_data".
# Includes both flat legacy keys and nested group keys for backward compat.
_KNOWN_META_KEYS = frozenset({
    "data_id", "memory", "memory_list", "trace_memory_id", "__trace_context__",
    # Plan 1+2+3 additions
    "owner", "channel_message", "source", "envelope", "envelope_id",
    "source_type", "user_id", "mimetype",
    # Provenance: copied through so agent and downstream see url / is_downloaded
    "url", "mime_type", "is_downloaded",
    # Nested group keys
    "identity", "content", "access", "tracing", "routing",
    # Additional flat keys
    "download_url", "gcs_uri", "session_id", "version", "version_label",
    "prompt", "crawl",
    # Dead fields (still recognized for splitting, dropped by normalization)
    "user_name", "name", "description", "tags", "subject",
    "llm_classification", "participants",
    "timestamp", "services", "device",
})

# Flat key → (group, nested_key) for flat→nested migration
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

# Plan 3 — source_type values that indicate a Universal Envelope payload
_ENVELOPE_SOURCE_TYPES = frozenset({
    "chat", "email", "conferencing", "document", "image", "video", "audio",
    "code", "vehicle", "satellite", "sensor", "telemetry", "geospatial",
    "medical", "financial", "scientific", "industrial", "infrastructure",
    "binary", "other",
})


def _build_owner(data: dict, meta: dict) -> dict | None:
    """Build a DataOwner-compatible dict from known payload fields.

    Extracts user identity (``user_id``, ``userId``, ``sender`` …) and
    channel information to populate ``owner.user`` and ``owner.source``.
    Returns ``None`` if no relevant fields are found.
    """
    user_id = (
        data.get("user_id") or data.get("userId") or data.get("sender") or
        data.get("from_user") or data.get("owner") or
        meta.get("user_id")
    )
    channel_type = (
        data.get("channel_type") or data.get("channel") or
        meta.get("channel_type")
    )
    channel_id = data.get("channel_id") or data.get("room_id") or data.get("chat_id")
    peer_id = data.get("peer_id") or data.get("from_id") or data.get("sender_id")
    thread_id = data.get("thread_id") or data.get("reply_to") or data.get("thread")

    if not user_id and not channel_type:
        return None

    owner: dict = {}
    if user_id:
        owner["user"] = {"user_id": str(user_id)}
    if channel_type or channel_id or peer_id or thread_id:
        owner["source"] = {
            "channel": {
                "channel_type": str(channel_type or "unknown"),
                "channel_id": channel_id,
                "peer_id": peer_id,
                "thread_id": thread_id,
            }
        }
    return owner or None


def _promote_user_id(data: dict, meta: dict) -> None:
    """Ensure ``meta["user_id"]`` is set so downstream consumers (processor,
    agents) see it at the top level of telemetry without digging into nested
    owner structures."""
    if meta.get("user_id"):
        return
    uid = (
        ((meta.get("owner") or {}).get("user") or {}).get("user_id")
        or (data.get("origin") or {}).get("user_id")
        or data.get("user_id") or data.get("userId")
        or data.get("sender") or data.get("from_user")
    )
    if uid:
        meta["user_id"] = str(uid)


def _build_channel_message(data: dict, meta: dict) -> dict | None:
    """Build a ChannelMessage-compatible dict from known payload fields.

    Returns ``None`` when the payload does not look like a chat message.
    """
    channel_type = (
        data.get("channel_type") or data.get("channel") or meta.get("channel_type")
    )
    # Only build for explicit chat-style payloads
    if not channel_type:
        return None

    text = (
        data.get("text") or data.get("body") or data.get("message") or
        data.get("content") or data.get("caption")
    )
    attachments = data.get("attachments") or data.get("media") or []
    if isinstance(attachments, dict):
        attachments = [attachments]

    return {
        "channel_type": str(channel_type),
        "channel_id": data.get("channel_id") or data.get("room_id"),
        "thread_id": data.get("thread_id") or data.get("reply_to"),
        "peer_id": data.get("peer_id") or data.get("from_id"),
        "message_id": data.get("message_id") or data.get("id"),
        "text": text,
        "attachments": attachments,
    }


def _normalize_to_envelope(payload: dict) -> tuple[dict, dict] | None:
    """Detect whether *payload* is a Universal Envelope and normalise it.

    Returns (data, telemetry) for Pub/Sub, or ``None`` if the payload
    is not an envelope-shaped message.

    A payload is treated as an envelope when:
    - It has an ``"envelope"`` key (forwarded from the ingest endpoint), or
    - Its ``"source_type"`` value is one of the known UDE source types.
    """
    if "envelope" in payload:
        env = payload["envelope"]
        if not isinstance(env, dict):
            return None
        data = env
        meta: dict = {
            "envelope_id": payload.get("envelope_id") or env.get("envelope_id"),
            "source_type": (
                (env.get("origin") or {}).get("source_type") or
                payload.get("source_type") or "other"
            ),
        }
        if "__trace_context__" in payload:
            meta["__trace_context__"] = payload["__trace_context__"]
        return data, meta

    source_type = str(payload.get("source_type") or "").lower()
    if source_type in _ENVELOPE_SOURCE_TYPES:
        data = {k: v for k, v in payload.items() if k not in _KNOWN_META_KEYS}
        meta = {k: payload[k] for k in _KNOWN_META_KEYS if k in payload}
        meta.setdefault("source_type", source_type)
        return data, meta

    return None


def _normalize_payload(payload: dict) -> tuple[dict, dict]:
    """Normalize to (data, meta_data). Supports data+meta_data, data+telemetry, or flat input.

    - Input may have "data" and "meta_data" (preferred) or "data" and "telemetry";
      if both meta_data and telemetry exist, meta_data is used. Known meta keys
      (including data_id, url, is_downloaded, mime_type) at top level are merged
      into the chosen meta bucket. All keys in the chosen meta bucket are preserved.
    - Flat format: no "data"/"meta_data"/"telemetry"; known meta keys go into
      meta_data, everything else into data.
    - Envelope fast-path (Plan 3): ``source_type`` in a known UDE category or
      ``"envelope"`` key present → wrap accordingly.

    Returns (data, meta_data) for publishing as {"data": data, "meta_data": meta_data}.
    """
    # Plan 3 — envelope detection (before generic normalization)
    envelope_result = _normalize_to_envelope(payload)
    if envelope_result is not None:
        data, meta = envelope_result
        if "owner" not in meta:
            owner = _build_owner(data, meta)
            if owner:
                meta["owner"] = owner
        if "channel_message" not in meta:
            ch_msg = _build_channel_message(data, meta)
            if ch_msg:
                meta["channel_message"] = ch_msg
        _promote_user_id(data, meta)
        meta = _nest_meta(meta)
        return data, meta

    # Prefer "meta_data" over "telemetry" when both present
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

    if "owner" not in meta:
        owner = _build_owner(data, meta)
        if owner:
            meta["owner"] = owner
    if "channel_message" not in meta:
        ch_msg = _build_channel_message(data, meta)
        if ch_msg:
            meta["channel_message"] = ch_msg
    _promote_user_id(data, meta)

    # Migrate to nested group structure
    meta = _nest_meta(meta)
    return data, meta


# ---------------------------------------------------------------------------
# Inline telemetry helpers — writes OTel spans to the inherited trace memory
# ---------------------------------------------------------------------------

_TELEMETRY_TIMEOUT_S = 10
_PIPELINE_LABEL = "api → receiver → pubsub → processor → agent"

_DEFAULT_TELEMETRY_MEMORY_ID = "telemetry-webhook-pipeline"
_telemetry_memory_ensured: bool = False


def _ensure_telemetry_memory() -> None:
    """Idempotently create the default telemetry memory if it is missing.

    Used as a fallback destination when the incoming payload does not carry
    a ``trace_memory_id``.  The check runs at most once per process lifetime.
    """
    global _telemetry_memory_ensured
    if _telemetry_memory_ensured or not _MEM_DOG_API_URL:
        return
    base = f"{_MEM_DOG_API_URL}/api/v1/memories"
    try:
        resp = _requests.get(
            f"{base}/{_DEFAULT_TELEMETRY_MEMORY_ID}", timeout=_TELEMETRY_TIMEOUT_S
        )
        if resp.status_code == 200:
            _telemetry_memory_ensured = True
            return
    except Exception:
        pass
    try:
        resp = _requests.post(
            base,
            json={
                "memory_id": _DEFAULT_TELEMETRY_MEMORY_ID,
                "memory_type": "telemetry",
                "name": "Webhook Pipeline Telemetry",
                "description": (
                    "OpenTelemetry-compatible spans for every stage of the "
                    "webhook pipeline: receiver → Pub/Sub → processor → "
                    "agent → sub-agent."
                ),
                "user_id": _DEFAULT_USER_UUID,
                "metadata": {
                    "source": "webhook_pipeline",
                    "pipeline": _PIPELINE_LABEL,
                    "otel_compatible": True,
                    "auto_created": True,
                },
            },
            timeout=_TELEMETRY_TIMEOUT_S,
        )
        resp.raise_for_status()
        _telemetry_memory_ensured = True
        logger.info("Created telemetry memory: %s", _DEFAULT_TELEMETRY_MEMORY_ID)
    except Exception as exc:
        logger.warning("Could not ensure telemetry memory: %s", exc)


def _generate_trace_id() -> str:
    """Return a 128-bit trace ID as a 32-char lowercase hex string."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:0] or uuid.uuid4().hex


def _generate_span_id() -> str:
    """Return a 64-bit span ID as a 16-char lowercase hex string."""
    return uuid.uuid4().hex[:16]


def _write_telemetry_span(
    *,
    trace_id: str,
    span_id: str,
    name: str,
    stage: str,
    service_name: str,
    service_type: str,
    status_code: str,
    kind: str,
    start_time: datetime,
    end_time: datetime,
    memory_id: str | None = None,
    parent_span_id: str | None = None,
    attributes: dict | None = None,
    events: list | None = None,
    user_id: str | None = None,
) -> None:
    """Write a best-effort OTel span to the trace memory.

    Uses the upstream ``trace_memory_id`` when provided, otherwise falls
    back to the default ``telemetry-webhook-pipeline`` memory.
    """
    if not _MEM_DOG_API_URL:
        return

    if not memory_id:
        _ensure_telemetry_memory()
        memory_id = _DEFAULT_TELEMETRY_MEMORY_ID

    duration_ms = (end_time - start_time).total_seconds() * 1000

    span: dict = {
        "trace_id": trace_id,
        "span_id": span_id,
        "name": name,
        "kind": kind,
        "service_name": service_name,
        "service_type": service_type,
        "status": {"code": status_code, "message": ""},
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_ms": round(duration_ms, 3),
        "pipeline": _PIPELINE_LABEL,
    }
    if parent_span_id:
        span["parent_span_id"] = parent_span_id
    if attributes:
        span["attributes"] = attributes
    if events:
        span["events"] = events

    tags = [
        f"trace_id:{trace_id}",
        f"span_id:{span_id}",
        f"stage:{stage}",
        f"service:{service_name}",
        f"status:{status_code}",
        f"kind:{kind}",
        "source:webhook_telemetry",
    ]
    if parent_span_id:
        tags.append(f"parent_span_id:{parent_span_id}")

    post_data: dict = {
        "content": json.dumps(span, default=str),
        "name": f"{name} | {status_code}",
        "description": f"[{service_name}] {name} — {kind} span — {status_code}",
        "tags": ",".join(tags),
        "memory_ids": memory_id,
        "exclusive": "true",
        "owner_user_id": user_id or _DEFAULT_USER_UUID,
    }

    try:
        resp = _requests.post(
            f"{_MEM_DOG_API_URL}/api/v1/data",
            data=post_data,
            timeout=_TELEMETRY_TIMEOUT_S,
        )
        resp.raise_for_status()
        logger.info(
            "Telemetry span written | trace=%s span=%s name=%s",
            trace_id[:8], span_id[:8], name,
        )
    except Exception as exc:
        logger.warning("Failed to write telemetry span (name=%s): %s", name, exc)


def _get_publisher() -> pubsub_v1.PublisherClient:
    """Lazy-init the Pub/Sub publisher client (reused across invocations)."""
    global _publisher
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


@functions_framework.http
def webhook_receiver(request: Request):
    """Receive a webhook payload and publish it to Pub/Sub.

    Accepts POST requests with a JSON body. The entire payload is published
    as a Pub/Sub message for asynchronous processing by the processor function.

    A ``trace_id`` and root ``span_id`` are generated for each accepted
    request and embedded in the Pub/Sub message attributes so downstream
    stages can attach their own spans to the same trace.

    Returns:
        202 Accepted on success.
        400 Bad Request if the body is missing or not valid JSON.
        405 Method Not Allowed for non-POST requests.
        413 Payload Too Large if the body exceeds MAX_PAYLOAD_BYTES.
    """
    if request.method != "POST":
        return jsonify({"error": "Method not allowed. Use POST."}), 405

    content_length = request.content_length or 0
    if content_length > MAX_PAYLOAD_BYTES:
        return jsonify({
            "error": f"Payload too large. Maximum size is {MAX_PAYLOAD_BYTES} bytes."
        }), 413

    raw_body = request.get_data(as_text=True)
    if not raw_body:
        return jsonify({"error": "Request body is empty."}), 400

    # --- Generate trace IDs for this webhook invocation ---
    trace_id = _generate_trace_id()
    span_id = _generate_span_id()
    span_start = datetime.now(timezone.utc)

    span_events: list[dict] = [
        {"name": "request_received", "timestamp": span_start.isoformat()},
    ]

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Invalid JSON: {exc}"}), 400

    if not isinstance(payload, dict):
        return jsonify({"error": "Payload must be a JSON object."}), 400

    # Publish in canonical form { data, meta_data } so processor and any other subscribers see the same shape.
    data, meta_data = _normalize_payload(payload)
    payload = {"data": data, "meta_data": meta_data}

    # Inherit trace_memory_id from upstream (created by the originating service)
    trace_memory_id: str | None = (
        (meta_data.get("tracing") or {}).get("trace_memory_id")
        or meta_data.get("trace_memory_id")
        or None
    )

    span_events.append(
        {"name": "payload_validated", "timestamp": datetime.now(timezone.utc).isoformat()}
    )

    received_at = span_start.isoformat()
    topic_path = _get_publisher().topic_path(PROJECT_ID, PUBSUB_TOPIC)

    message_data = json.dumps(payload).encode("utf-8")
    attributes = {
        "received_at": received_at,
        "source": "webhook",
        "content_type": request.content_type or "application/json",
        "x-trace-id": trace_id,
        "x-span-id": span_id,
    }
    if trace_memory_id:
        attributes["x-trace-memory-id"] = trace_memory_id
    resolved_user_id = (
        (meta_data.get("identity") or {}).get("user_id")
        or meta_data.get("user_id")
        or _DEFAULT_USER_UUID
    )
    attributes["x-user-id"] = str(resolved_user_id)

    future = _get_publisher().publish(topic_path, data=message_data, **attributes)
    message_id = future.result()

    span_end = datetime.now(timezone.utc)
    span_events.append(
        {"name": "pubsub_published", "timestamp": span_end.isoformat()}
    )

    logger.info(
        "Webhook payload published to Pub/Sub",
        extra={
            "pubsub_message_id": message_id,
            "topic": PUBSUB_TOPIC,
            "payload_size": len(message_data),
            "received_at": received_at,
            "trace_id": trace_id,
            "span_id": span_id,
            "trace_memory_id": trace_memory_id or "",
        },
    )

    _write_telemetry_span(
        trace_id=trace_id,
        span_id=span_id,
        name="webhook.receiver",
        stage="receiver",
        service_name="webhook-receiver",
        service_type="gcp_cloud_function_http",
        status_code="OK",
        kind="SERVER",
        start_time=span_start,
        end_time=span_end,
        memory_id=trace_memory_id,
        user_id=resolved_user_id,
        attributes={
            "http.method": "POST",
            "pubsub.topic": PUBSUB_TOPIC,
            "pubsub.message_id": message_id,
            "payload_size_bytes": len(message_data),
            "content_type": request.content_type or "application/json",
            "payload_keys": list(payload.keys()),
        },
        events=span_events,
    )

    return jsonify({
        "status": "accepted",
        "message_id": message_id,
        "received_at": received_at,
        "trace_id": trace_id,
    }), 202
