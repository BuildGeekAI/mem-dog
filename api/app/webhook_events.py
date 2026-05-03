"""Webhook event dispatch for upload notifications.

When data is uploaded via POST /api/v1/data with ``forward_to_webhook=true``,
dispatches a ``data.uploaded`` event to the webhook pipeline with a canonical
payload: ``{ "data": {...}, "meta_data": {...} }``.

This module acts as a **trace origin**: it creates a per-dispatch ``tracing``
memory and embeds its ``memory_id`` as ``trace_memory_id`` inside the
``meta_data`` payload.  Downstream services (receiver, processor, agent)
inherit the ID and write their OTel spans to the same memory.

meta_data uses a nested group structure (identity, content, access, tracing)
so receiver, processor, and agent preserve fields end-to-end.  By default
webhook dispatch is off; the Testing tab in the UI passes the flag when
uploading.

The sender (API) must have permission to write to the pipeline receiver (valid
WEBHOOK_GATEWAY_URL and WEBHOOK_API_KEY). If the POST to the receiver fails
(e.g. 403, 401, network error), the error is published to the webhook dispatch
error memory (``timeline-webhook-dispatch-errors``) so it can be inspected and
fixed.

Runs as a background task; best-effort — never raises.
"""

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import httpx

from app import config
from app.models import MemoryCreate, MemoryType

if TYPE_CHECKING:
    from app.storage import Storage

logger = logging.getLogger("mem_dog.webhook_events")

_WEBHOOK_TIMEOUT_S = 15
DISPATCH_ERROR_MEMORY_ID = "timeline-webhook-dispatch-errors"
DISPATCH_ERROR_USER_ID = config.DEFAULT_USER_ID

_dispatch_error_memory_ensured: bool = False


def _ensure_dispatch_error_memory(storage: "Storage") -> None:
    """Idempotently create the webhook dispatch error timeline so we can write failures."""
    global _dispatch_error_memory_ensured
    if _dispatch_error_memory_ensured:
        return
    try:
        if not config.is_memories_enabled():
            return
        if storage.get_memory(DISPATCH_ERROR_MEMORY_ID) is not None:
            _dispatch_error_memory_ensured = True
            return
        storage.create_memory(
            MemoryCreate(
                memory_type=MemoryType.TIMELINE,
                name="Webhook Dispatch Errors",
                description=(
                    "Records when the API failed to send a data.uploaded event to the "
                    "webhook pipeline (e.g. permission denied, invalid API key). "
                    "Inspect this memory to fix webhook gateway configuration."
                ),
                user_id=DISPATCH_ERROR_USER_ID,
                metadata={
                    "source": "webhook_dispatch",
                    "auto_created": True,
                },
            ),
            memory_id_override=DISPATCH_ERROR_MEMORY_ID,
        )
        _dispatch_error_memory_ensured = True
        logger.info("Created webhook dispatch error memory: %s", DISPATCH_ERROR_MEMORY_ID)
    except Exception as exc:
        logger.warning("Could not ensure webhook dispatch error memory: %s", exc)


def _write_dispatch_error_to_memory(
    storage: "Storage",
    data_id: str,
    status_code: Optional[int] = None,
    response_body: Optional[str] = None,
    exception_message: Optional[str] = None,
) -> None:
    """Write a webhook dispatch failure to the agent error memory. Best-effort; never raises."""
    try:
        _ensure_dispatch_error_memory(storage)
        event = {
            "event": "webhook_dispatch_failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_id": data_id,
            "status_code": status_code,
            "response_body": (response_body or "")[:500],
            "exception": exception_message,
        }
        storage.create_data(
            content=json.dumps(event, default=str).encode("utf-8"),
            content_type="application/json",
            user=DISPATCH_ERROR_USER_ID,
            memory_ids=[DISPATCH_ERROR_MEMORY_ID],
            tags=["source:webhook_dispatch", "status:error", "event:webhook_dispatch_failed"],
            name="webhook dispatch failed",
            description=f"Failed to send data_id={data_id} to webhook pipeline",
            exclusive_memory_ids=True,
        )
        logger.info(
            "Webhook dispatch error written to memory | data_id=%s status_code=%s",
            data_id, status_code,
        )
    except Exception as exc:
        logger.warning("Could not write webhook dispatch error to memory: %s", exc)


def _create_trace_memory(storage: "Storage", user_id: str, data_id: str) -> Optional[str]:
    """Create a per-dispatch tracing memory.  Returns the memory_id or None on failure."""
    if not config.is_memories_enabled():
        return None
    try:
        mem = storage.create_memory(
            MemoryCreate(
                memory_type=MemoryType.TRACING,
                name=f"Webhook trace — {data_id}",
                description="Per-dispatch trace container for OTel spans",
                user_id=user_id,
                metadata={"source": "webhook_dispatch", "data_id": data_id, "auto_created": True},
            )
        )
        logger.info("Created trace memory %s for data_id=%s", mem.memory_id, data_id)
        return mem.memory_id
    except Exception as exc:
        logger.warning("Could not create trace memory for data_id=%s: %s", data_id, exc)
        return None


def _build_memory_dict(
    memory_ids: List[str],
    trace_memory_id: Optional[str] = None,
) -> dict:
    """Group memory IDs by type prefix into ``{ <memory_type>: [<ids>] }``.

    IDs following the ``<type>-<suffix>`` convention are bucketed under the
    type prefix (``timeline``, ``session``, ``conversation``, ``telemetry``).
    Unrecognised prefixes are kept as-is so no information is lost.

    The *trace_memory_id* (whose ID may be auto-generated without a prefix)
    is placed into the ``tracing`` bucket.
    """
    _TYPE_PREFIXES = {
        "timeline", "session", "conversation", "telemetry", "tracing",
    }
    result: dict[str, list[str]] = {}
    for mid in memory_ids:
        prefix = mid.split("-", 1)[0] if "-" in mid else "other"
        if prefix not in _TYPE_PREFIXES:
            prefix = "other"
        result.setdefault(prefix, []).append(mid)
    if trace_memory_id:
        tracing_list = result.setdefault("tracing", [])
        if trace_memory_id not in tracing_list:
            tracing_list.append(trace_memory_id)
    return {k: v for k, v in result.items() if v}


def dispatch_upload_event(
    storage: "Storage",
    data_id: str,
    base_url: str,
    content_type: str,
    user_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    memory_ids: Optional[List[str]] = None,
    url: Optional[str] = None,
    mime_type: Optional[str] = None,
    is_downloaded: bool = False,
) -> None:
    """Dispatch a data.uploaded event to the webhook pipeline.

    The meta_data payload carries a structured ``memory`` dict keyed by
    memory type (``timeline``, ``session``, ``tracing``, …) so every
    downstream service uses the same format::

        "memory": {
            "timeline": ["timeline-<user_id>"],
            "session":  ["session-abc"],
            "tracing":  ["<trace_memory_id>"],
        }

    On failure the error is published to
    ``timeline-webhook-dispatch-errors``.

    Intended to run as a FastAPI BackgroundTasks task. Best-effort — never
    raises. Logs and swallows all exceptions.

    Args:
        storage: Storage instance for metadata and user lookups.
        data_id: Created data item ID.
        base_url: API base URL for constructing data_url.
        content_type: MIME type (e.g. image/png, application/json).
        user_id: Owner user ID.
        name: User-friendly name (optional).
        description: Description (optional).
        tags: Tags (optional).
        memory_ids: Caller-provided memory IDs; resolved IDs fetched from
            metadata if available.
        url: Remote URL the content was fetched from (optional).
        mime_type: Declared or detected MIME type (optional).
        is_downloaded: Whether the content is already stored (no re-download needed).
    """
    gateway_url = (config.WEBHOOK_GATEWAY_URL or "").strip()
    api_key = (config.WEBHOOK_API_KEY or "").strip()
    if not gateway_url or not api_key:
        logger.error(
            "dispatch_upload_event called but webhook gateway is not configured "
            "(gateway_url=%r, api_key=%s) — data_id=%s will not be forwarded",
            gateway_url, "set" if api_key else "missing", data_id,
        )
        return

    try:
        data_url = f"{base_url.rstrip('/')}/api/v1/data/{data_id}"

        resolved_memory_ids: List[str] = list(memory_ids) if memory_ids else []
        version_label: str = ""
        try:
            metadata = storage.get_metadata(data_id, user_id)
            if metadata and metadata.memory_ids:
                resolved_memory_ids = metadata.memory_ids
            if metadata and getattr(metadata, "data_version_label", None):
                version_label = metadata.data_version_label
        except Exception as exc:
            logger.debug("Could not fetch metadata for %s: %s", data_id, exc)

        user_timeline_id = f"timeline-{user_id}"
        if user_timeline_id not in resolved_memory_ids:
            resolved_memory_ids.insert(0, user_timeline_id)

        trace_memory_id = _create_trace_memory(storage, user_id, data_id)

        memory_dict = _build_memory_dict(resolved_memory_ids, trace_memory_id)

        # Build nested meta_data — content is always stored by this point,
        # so is_downloaded is always True for dispatch.
        effective_mime = mime_type or content_type or None

        access_block: dict = {
            "data_id": data_id,
            "is_downloaded": True,
            "download_url": data_url,
        }
        if url is not None:
            access_block["url"] = url
        if config.RAW_BUCKET and version_label:
            access_block["gcs_uri"] = (
                f"gs://{config.RAW_BUCKET}/{user_id}/{data_id}/{version_label}/data"
            )

        tracing_block: dict = {"memory": memory_dict}
        if trace_memory_id:
            tracing_block["trace_memory_id"] = trace_memory_id

        meta_data: dict = {
            "identity": {"user_id": user_id},
            "content": {"mime_type": effective_mime} if effective_mime else {},
            "access": access_block,
            "tracing": tracing_block,
        }
        payload = {
            "data": {
                "url": data_url,
                "payload": {
                    "event": "data.uploaded",
                    "data_url": data_url,
                    "data_id": data_id,
                    "name": name,
                    "description": description,
                    "tags": tags or [],
                },
            },
            "meta_data": meta_data,
        }

        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=_WEBHOOK_TIMEOUT_S) as client:
            resp = client.post(gateway_url, json=payload, headers=headers)

        if resp.status_code >= 400:
            logger.error(
                "Webhook dispatch failed | data_id=%s status=%d body=%s",
                data_id, resp.status_code, resp.text[:200],
            )
            _write_dispatch_error_to_memory(
                storage,
                data_id=data_id,
                status_code=resp.status_code,
                response_body=resp.text,
            )
        else:
            logger.info(
                "Webhook event dispatched | data_id=%s status=%d",
                data_id, resp.status_code,
            )
    except Exception as exc:
        logger.error(
            "Failed to dispatch upload event for %s: %s", data_id, exc,
            exc_info=True,
        )
        _write_dispatch_error_to_memory(
            storage,
            data_id=data_id,
            exception_message=str(exc),
        )
