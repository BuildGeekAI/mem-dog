"""Webhook Processor Cloud Function.

Pub/Sub-triggered Cloud Function that receives webhook messages and sends
them to the ADK agent hosted on Cloud Run for processing (logging + routing
+ storage in the agent's own memory).

The agent runs as a persistent Cloud Run service (``adk api_server``).  Each
webhook creates an ephemeral in-memory session, invokes the agent via a
single HTTP POST to ``/run``, then discards the session.  Session state is
never persisted between webhooks — the agent is stateless.

Fire-and-forget dispatch
------------------------
The agent call is dispatched in a background thread so the Cloud Function
returns immediately.  Pub/Sub ACKs the message as soon as the function
returns, preventing retries caused by agent latency.  The background thread
writes the telemetry span once the agent call completes or fails.

Telemetry
---------
The receiver embeds ``x-trace-id`` and ``x-span-id`` in the Pub/Sub message
attributes.  This function:
1. Extracts those IDs (falling back to fresh UUIDs for messages sent before
   this change was deployed).
2. Generates its own ``processor_span_id``.
3. Injects ``{"__trace_context__": {...}}`` into the payload dict so the ADK
   agent can pop it and attach its own spans to the same trace.
4. Writes a single OTel-compatible processor span to the inherited
   ``trace_memory_id`` after the agent call completes (or fails).
"""

import base64
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone

import functions_framework
import google.auth.transport.requests as google_requests
import google.oauth2.id_token
import requests
from cloudevents.http import CloudEvent

logger = logging.getLogger("mem_dog.webhook.processor")

AGENT_SERVICE_URL: str = os.environ.get("AGENT_SERVICE_URL", "").rstrip("/")
_MEM_DOG_API_URL: str = os.environ.get("MEM_DOG_API_URL", "").rstrip("/")


_RUN_TIMEOUT_S: int = int(os.environ.get("AGENT_RUN_TIMEOUT_S", "300"))

# ---------------------------------------------------------------------------
# Inline telemetry helpers — writes OTel spans to the inherited trace memory
# ---------------------------------------------------------------------------

_TELEMETRY_TIMEOUT_S = 10
_PIPELINE_LABEL = "api → receiver → pubsub → processor → agent"

_DEFAULT_USER_UUID = "00000000-0000-0000-0000-000000000001"
_SYSTEM_USER_ID: str = os.environ.get("SYSTEM_USER_ID", _DEFAULT_USER_UUID)

_KNOWN_META_KEYS = frozenset({
    "user_id", "data_id", "version", "version_label", "timestamp",
    "memory", "memory_list", "trace_memory_id", "__trace_context__",
    "session_id", "services", "device",
    # Provenance: copied through so agent sees url / is_downloaded
    "url", "mime_type", "is_downloaded", "mimetype",
    # Nested group keys
    "identity", "content", "access", "tracing", "routing",
    # Additional flat keys
    "owner", "channel_message", "source_type", "download_url", "gcs_uri",
    "prompt", "crawl",
    # Dead fields
    "user_name", "name", "description", "tags", "subject",
    "llm_classification", "participants", "envelope_id",
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

_REMOVED_FIELDS_PROC = frozenset({
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
        if key in _REMOVED_FIELDS_PROC:
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

def _normalize_payload(payload: dict) -> tuple[dict, dict]:
    """Normalize to (data, meta_data). Accepts data+meta_data, data+telemetry, or flat format.

    Prefers "meta_data" over "telemetry" when both are present. All keys in the
    chosen meta_data bucket are preserved (including data_id, url, is_downloaded,
    mime_type). Returns (data, meta_dict) for internal use; the payload sent to
    the agent uses keys "data" and "meta_data".
    """
    if not isinstance(payload, dict):
        return (payload if isinstance(payload, dict) else {"raw": str(payload)}), {}

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
        return data, _nest_meta(meta)
    meta = {k: payload[k] for k in _KNOWN_META_KEYS if k in payload}
    data = {k: v for k, v in payload.items() if k not in _KNOWN_META_KEYS}
    return data, _nest_meta(meta)


def _create_tracing_memory(user_id: str | None = None) -> str | None:
    """Create a per-invocation tracing memory via the mem-dog API. Returns memory_id or None."""
    if not _MEM_DOG_API_URL:
        return None
    uid = user_id or _SYSTEM_USER_ID
    try:
        resp = requests.post(
            f"{_MEM_DOG_API_URL}/api/v1/memories",
            json={
                "memory_type": "tracing",
                "description": "Per-invocation trace container for OTel spans",
                "user_id": uid,
                "metadata": {"source": "webhook_processor", "auto_created": True},
            },
            timeout=_TELEMETRY_TIMEOUT_S,
        )
        resp.raise_for_status()
        memory_id = resp.json().get("memory_id")
        if memory_id:
            logger.info("Created tracing memory: %s", memory_id)
        return memory_id
    except Exception as exc:
        logger.warning("Could not create tracing memory: %s", exc)
        return None


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
    parent_span_id: str | None = None,
    attributes: dict | None = None,
    memory_id: str | None = None,
    purpose: str | None = None,
    user_id: str | None = None,
    data_id: str | None = None,
    version: int | None = None,
    version_label: str | None = None,
) -> None:
    """Write a best-effort OTel span to the inherited trace memory.

    Spans are only written when *memory_id* (the upstream ``trace_memory_id``)
    is provided.  The processor never creates tracing memories itself.
    """
    if not _MEM_DOG_API_URL or not memory_id:
        return
    target_memory = memory_id
    uid = user_id or _SYSTEM_USER_ID

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

    # Merge canonical EventMeta fields into attributes (caller values take precedence)
    enriched: dict = dict(attributes or {})
    if user_id:
        enriched.setdefault("user_id", user_id)
    if data_id:
        enriched.setdefault("data_id", data_id)
    if version is not None:
        enriched.setdefault("version", version)
    if version_label:
        enriched.setdefault("version_label", version_label)
    if enriched:
        span["attributes"] = enriched

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
    # Canonical EventMeta tags for filtering/search
    if user_id:
        tags.append(f"user_id:{user_id}")
    if data_id:
        tags.append(f"data_id:{data_id}")
    if version is not None:
        tags.append(f"version:{version}")

    post_data = {
        "content": json.dumps(span, default=str),
        "name": f"{name} | {status_code}",
        "description": f"[{service_name}] {name} — {kind} span — {status_code}",
        "tags": ",".join(tags),
        "memory_ids": target_memory,
        "exclusive": "true",
        "owner_user_id": uid,
    }
    if purpose:
        post_data["purpose"] = purpose

    try:
        resp = requests.post(
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


# ---------------------------------------------------------------------------
# Identity token helper
# ---------------------------------------------------------------------------

def _identity_token(audience: str) -> str | None:
    """Fetch a Google-signed ID token for the given Cloud Run service URL.

    Required because the agent Cloud Run service is deployed with
    ``--no-allow-unauthenticated``.  The Cloud Function's service account
    must have ``roles/run.invoker`` on the service (granted by deploy-agent).

    Returns ``None`` when running locally (no GCP metadata server available),
    in which case no ``Authorization`` header is sent.  The local
    ``adk api_server`` does not require authentication.

    Args:
        audience: The full Cloud Run service URL (used as the token audience).

    Returns:
        A signed ID token string, or ``None`` when running locally.
    """
    try:
        auth_req = google_requests.Request()
        return google.oauth2.id_token.fetch_id_token(auth_req, audience)
    except Exception as exc:
        logger.debug(
            "Could not fetch identity token (running locally?): %s", exc
        )
        return None


def _run_agent(payload: dict, *, max_retries: int = 3) -> dict:
    """Send the webhook payload to the agent's direct /process-webhook endpoint.

    Calls ``POST /process-webhook`` on the agent service, which invokes
    ``route_payload()`` directly — no LLM orchestration layer.  This is
    reliable and fast regardless of the underlying model's tool-calling
    ability.

    Retries up to ``max_retries`` times on transient SSL/connection errors.

    Args:
        payload: The decoded webhook JSON payload, optionally enriched with
            ``__trace_context__``.
        max_retries: Number of attempts before giving up.

    Returns:
        The routing result dict from the agent (data_type, user_id, etc.).

    Raises:
        RuntimeError: If ``AGENT_SERVICE_URL`` is not set or all retries fail.
        requests.HTTPError: If the agent returns a non-2xx status.
    """
    if not AGENT_SERVICE_URL:
        raise RuntimeError(
            "AGENT_SERVICE_URL is not set.  Deploy the agent to Cloud Run "
            "first and set the env var on this function."
        )

    payload_json = json.dumps(payload)
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        token = _identity_token(AGENT_SERVICE_URL)
        auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

        try:
            with requests.Session() as http:
                http.headers.update(auth_headers)
                resp = http.post(
                    f"{AGENT_SERVICE_URL}/process-webhook",
                    json={"payload_json": payload_json},
                    timeout=_RUN_TIMEOUT_S,
                )
                resp.raise_for_status()
                result = resp.json()

            logger.info(
                "Agent routed webhook directly",
                extra={
                    "data_type": result.get("data_type"),
                    "user_id": result.get("user_id"),
                    "attempt": attempt,
                    "payload_keys": list(payload.keys()) if isinstance(payload, dict) else [],
                },
            )
            return result

        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            logger.warning(
                "Agent call attempt %d/%d failed (transient): %s — retrying",
                attempt, max_retries, exc,
            )
        except Exception:
            raise

    raise RuntimeError(
        f"Agent call failed after {max_retries} attempts: {last_exc}"
    )


@functions_framework.cloud_event
def webhook_processor(cloud_event: CloudEvent) -> None:
    """Process a Pub/Sub message containing a webhook payload.

    Decodes the Pub/Sub message data, extracts the JSON payload, and
    sends it to the ADK agent on Cloud Run for processing.  Writes an
    OTel-compatible processor span to the inherited trace memory
    on completion.

    Trace context (``x-trace-id``, ``x-span-id``) is extracted from the
    Pub/Sub message attributes and propagated into the payload under the
    ``__trace_context__`` key so the agent can link its spans to this trace.

    Args:
        cloud_event: The CloudEvent wrapping the Pub/Sub message.
    """
    if not AGENT_SERVICE_URL:
        logger.error(
            "AGENT_SERVICE_URL not set.  Deploy the agent to Cloud Run "
            "first and set the env var on this function."
        )
        return

    message_data = cloud_event.data.get("message", {}).get("data", "")

    if not message_data:
        logger.warning("Received empty Pub/Sub message, skipping.")
        return

    try:
        decoded = base64.b64decode(message_data).decode("utf-8")
        payload = json.loads(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to decode Pub/Sub message: %s", exc)
        return

    if not isinstance(payload, dict):
        payload = {"raw": payload}

    # Normalize to data + meta_data; ensure per-invocation trace memory
    data, meta_data = _normalize_payload(payload)
    payload = {"data": data, "meta_data": meta_data}

    message = cloud_event.data.get("message", {})
    pubsub_message_id = message.get("messageId", "unknown")
    attributes = message.get("attributes", {})
    payload_keys = list(data.keys()) if isinstance(data, dict) else []

    # Extract or generate trace context
    trace_id: str = attributes.get("x-trace-id") or (
        uuid.uuid4().hex + uuid.uuid4().hex[:0] or uuid.uuid4().hex
    )
    receiver_span_id: str | None = attributes.get("x-span-id") or None
    processor_span_id = _generate_span_id()

    # Extract EventMeta fields from Pub/Sub attributes or nested meta_data
    event_user_id: str = (
        attributes.get("x-user-id")
        or (meta_data.get("identity") or {}).get("user_id")
        or meta_data.get("user_id")
        or _SYSTEM_USER_ID
    )
    event_data_id: str | None = (
        attributes.get("x-data-id")
        or (meta_data.get("access") or {}).get("data_id")
        or meta_data.get("data_id")
        or None
    )
    event_version_raw = (
        attributes.get("x-version")
        or (meta_data.get("tracing") or {}).get("version")
        or meta_data.get("version")
    )
    event_version: int | None = int(event_version_raw) if event_version_raw else None
    event_version_label: str | None = (
        (meta_data.get("tracing") or {}).get("version_label")
        or meta_data.get("version_label")
        or None
    )

    # Propagate canonical meta fields into nested meta_data
    meta_data.setdefault("identity", {}).setdefault("user_id", event_user_id)
    if event_data_id:
        meta_data.setdefault("access", {}).setdefault("data_id", event_data_id)
    if event_version is not None:
        meta_data.setdefault("tracing", {}).setdefault("version", event_version)
    if event_version_label:
        meta_data.setdefault("tracing", {}).setdefault("version_label", event_version_label)

    # Inherit trace_memory_id from upstream (Pub/Sub attributes or payload).
    # Only create a new tracing memory when no upstream trace exists.
    existing_trace_mem = (meta_data.get("tracing") or {}).get("trace_memory_id")
    if not existing_trace_mem:
        meta_data.setdefault("tracing", {})["trace_memory_id"] = (
            attributes.get("x-trace-memory-id")
            or _create_tracing_memory(user_id=event_user_id)
        )

    meta_data["__trace_context__"] = {
        "trace_id": trace_id,
        "parent_span_id": processor_span_id,
        "receiver_span_id": receiver_span_id,
    }

    span_start = datetime.now(timezone.utc)

    logger.info(
        "Processing webhook payload from Pub/Sub",
        extra={
            "message_id": pubsub_message_id,
            "received_at": attributes.get("received_at", "unknown"),
            "payload_keys": payload_keys,
            "trace_id": trace_id,
        },
    )

    # Write a RUNNING span to the per-invocation trace memory (skipped if no trace memory)
    _write_telemetry_span(
        trace_id=trace_id,
        span_id=processor_span_id,
        name="webhook.processor",
        stage="processor",
        service_name="webhook-processor",
        service_type="gcp_cloud_function_pubsub",
        status_code="RUNNING",
        kind="CONSUMER",
        start_time=span_start,
        end_time=span_start,
        parent_span_id=receiver_span_id,
        memory_id=(meta_data.get("tracing") or {}).get("trace_memory_id"),
        purpose="trace_stage",
        user_id=event_user_id,
        data_id=event_data_id,
        version=event_version,
        version_label=event_version_label,
        attributes={
            "pubsub.message_id": pubsub_message_id,
            "agent_service_url": AGENT_SERVICE_URL,
            "original_received_at": attributes.get("received_at", ""),
            "payload_keys": payload_keys,
            "user_id": event_user_id,
            "data_id": event_data_id or "",
        },
    )

    def _agent_task() -> None:
        """Call the agent in the background; telemetry is written by the agent itself."""
        try:
            _run_agent(payload)
        except Exception as exc:
            logger.exception("Background agent call failed: %s", exc)

    # Fire and forget — return immediately so Pub/Sub ACKs the message.
    # The background thread continues running in the Cloud Run container.
    thread = threading.Thread(target=_agent_task, daemon=False)
    thread.start()
    logger.info(
        "Payload dispatched to agent (fire-and-forget)",
        extra={
            "message_id": pubsub_message_id,
            "trace_id": trace_id,
            "agent_service_url": AGENT_SERVICE_URL,
        },
    )
