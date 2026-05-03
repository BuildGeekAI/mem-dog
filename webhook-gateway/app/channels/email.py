"""Email channel adapter.

Supports inbound email webhook formats from SendGrid Inbound Parse and
Mailgun.  Extracts sender, recipients, subject, body, and attachments,
then optionally classifies the email intent via Gemini 3 Flash.

SendGrid Inbound Parse sends attachment content inline in the multipart
POST (keys like ``attachment1``, ``attachment2``).  We base64-encode the
raw bytes so the downloader can ingest them without a separate HTTP
fetch.  Mailgun stores attachment URLs in ``message.attachments[].url``.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage

_log = logging.getLogger("openclaw_gateway.channels.email")


def _extract_sendgrid(payload: dict[str, Any]) -> NormalizedMessage:
    """Normalise a SendGrid Inbound Parse webhook payload.

    SendGrid delivers attachment *content* inline in the multipart form
    data under keys ``attachment1``, ``attachment2``, etc.  The
    ``attachment-info`` JSON blob carries the corresponding metadata.
    We pair them together and base64-encode the content so the
    attachment downloader can ingest without a URL.
    """
    attachments: list[dict[str, Any]] = []
    att_info = payload.get("attachment-info")
    if isinstance(att_info, dict):
        for key, meta in att_info.items():
            att: dict[str, Any] = {
                "filename": meta.get("filename", key),
                "mime_type": meta.get("type", "application/octet-stream"),
            }
            # SendGrid multipart includes the file bytes under the same
            # key (e.g. "attachment1").  If the gateway framework has
            # already read it into payload, it will be bytes or a string.
            inline = payload.get(key)
            if isinstance(inline, bytes):
                att["content_b64"] = base64.b64encode(inline).decode("ascii")
            elif isinstance(inline, str) and inline:
                # Already text (unlikely for binary, but handle it)
                att["content_b64"] = base64.b64encode(inline.encode()).decode("ascii")
            attachments.append(att)

    return NormalizedMessage(
        channel_type="email",
        peer_id=payload.get("from", ""),
        channel_id=payload.get("to", ""),
        subject=payload.get("subject"),
        text=payload.get("text", ""),
        html=payload.get("html"),
        attachments=attachments,
        source_type="email",
        raw=payload,
    )


def _extract_mailgun(payload: dict[str, Any]) -> NormalizedMessage:
    """Normalise a Mailgun webhook payload.

    Mailgun ``message.attachments`` contain ``url``, ``content-type``,
    and ``name`` for each attachment — the URL is a temporary download
    link valid for a few hours.
    """
    event_data = payload.get("event-data") or payload
    msg = event_data.get("message", {}) if isinstance(event_data, dict) else {}
    headers = msg.get("headers", {})

    attachments: list[dict[str, Any]] = []
    for att in msg.get("attachments", []):
        if isinstance(att, dict):
            attachments.append({
                "filename": att.get("name", att.get("filename", "")),
                "mime_type": att.get("content-type", att.get("content_type", "application/octet-stream")),
                "url": att.get("url", ""),
            })

    return NormalizedMessage(
        channel_type="email",
        peer_id=headers.get("from", event_data.get("sender", "")),
        channel_id=headers.get("to", event_data.get("recipient", "")),
        message_id=headers.get("message-id"),
        subject=headers.get("subject"),
        text=msg.get("body", {}).get("text", "") if isinstance(msg.get("body"), dict) else "",
        html=msg.get("body", {}).get("html") if isinstance(msg.get("body"), dict) else None,
        attachments=attachments,
        source_type="email",
        raw=payload,
    )


class EmailAdapter(BaseChannelAdapter):
    """Adapter for inbound email webhooks (SendGrid / Mailgun)."""

    @property
    def channel_type(self) -> str:
        return "email"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        if "event-data" in payload or "signature" in payload:
            _log.debug("Detected Mailgun format")
            return _extract_mailgun(payload)

        _log.debug("Using SendGrid format (default)")
        return _extract_sendgrid(payload)
