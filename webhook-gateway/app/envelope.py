"""Build a UniversalEnvelope from a NormalizedMessage.

The envelope format matches what the existing webhook receiver and
downstream processor expect (``{"data": {...}, "meta_data": {...}}``).
Trace IDs follow the same OTel-compatible format used in
``webhook/receiver/main.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .channels.base import NormalizedMessage


def _generate_trace_id() -> str:
    """128-bit trace ID as a 32-char lowercase hex string."""
    return uuid.uuid4().hex


def _generate_span_id() -> str:
    """64-bit span ID as a 16-char lowercase hex string."""
    return uuid.uuid4().hex[:16]


def build_envelope(
    msg: NormalizedMessage,
    *,
    resolved_user_id: str | None = None,
    llm_classification: dict[str, Any] | None = None,
    data_id: str | None = None,
    is_downloaded: bool = False,
    mime_type: str | None = None,
    integrations: list[dict[str, Any]] | None = None,
    org_id: str | None = None,
    project_id: str | None = None,
    webhook_id: str | None = None,
) -> dict[str, Any]:
    """Convert a ``NormalizedMessage`` into the canonical envelope format.

    Returns a dict ready to be JSON-serialised and POSTed to the webhook
    gateway.  The ``trace_id`` and ``span_id`` are embedded in the
    ``meta_data`` section for downstream propagation.

    When ``data_id`` (and optionally ``is_downloaded``) are set, they are
    included in telemetry so the pipeline can skip duplicate write and
    process only once (memdog format).
    """
    trace_id = _generate_trace_id()
    span_id = _generate_span_id()
    now = datetime.now(timezone.utc).isoformat()

    content_payload: dict[str, Any] = dict(msg.raw) if msg.raw else {}
    if msg.text and "text" not in content_payload:
        content_payload["text"] = msg.text
    if msg.subject and "subject" not in content_payload:
        content_payload["subject"] = msg.subject
    if msg.html and "html" not in content_payload:
        content_payload["html"] = msg.html
    if msg.recording_url and "recording_url" not in content_payload:
        content_payload["recording_url"] = msg.recording_url

    owner: dict[str, Any] = {}
    uid = resolved_user_id or msg.user_id
    if uid:
        owner["user"] = {"user_id": uid}
    if msg.channel_type or msg.channel_id or msg.peer_id:
        owner["source"] = {
            "channel": {
                "channel_type": msg.channel_type,
                "channel_id": msg.channel_id,
                "peer_id": msg.peer_id,
                "thread_id": msg.thread_id,
            }
        }

    channel_message: dict[str, Any] | None = None
    if msg.text is not None or msg.attachments:
        channel_message = {
            "channel_type": msg.channel_type,
            "channel_id": msg.channel_id,
            "thread_id": msg.thread_id,
            "peer_id": msg.peer_id,
            "message_id": msg.message_id,
            "text": msg.text,
            "attachments": msg.attachments,
        }

    # Build nested meta_data
    identity_block: dict[str, Any] = {}
    if uid:
        identity_block["user_id"] = uid
    if owner:
        identity_block["owner"] = owner
    if org_id:
        identity_block["org_id"] = org_id
    if project_id:
        identity_block["project_id"] = project_id
    if webhook_id:
        identity_block["webhook_id"] = webhook_id

    content_block: dict[str, Any] = {"source_type": msg.source_type}
    effective_mime = mime_type or msg.mime_type
    if effective_mime:
        content_block["mime_type"] = effective_mime
    if channel_message:
        content_block["channel_message"] = channel_message

    effective_data_id = data_id or msg.data_id
    access_block: dict[str, Any] = {
        "is_downloaded": bool(is_downloaded or msg.is_downloaded),
    }
    if effective_data_id:
        access_block["data_id"] = effective_data_id
        content_payload["data_id"] = effective_data_id

    meta_data: dict[str, Any] = {
        "identity": identity_block,
        "content": content_block,
        "access": access_block,
        "__trace_context__": {
            "trace_id": trace_id,
            "span_id": span_id,
        },
    }

    if integrations:
        meta_data["integrations"] = integrations

    return {
        "data": {"payload": content_payload},
        "meta_data": meta_data,
        "_envelope_meta": {
            "trace_id": trace_id,
            "span_id": span_id,
            "created_at": now,
            "gateway": "webhook-gateway",
            "channel_type": msg.channel_type,
            "webhook_id": webhook_id,
        },
    }
