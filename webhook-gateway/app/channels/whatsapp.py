"""WhatsApp channel adapter.

Handles WhatsApp Cloud API webhook payloads (the format sent by Meta's
Graph API) and the Baileys-style event format used by OpenClaw's
WhatsApp channel.

Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


def _extract_cloud_api(payload: dict[str, Any]) -> NormalizedMessage:
    """Normalise a WhatsApp Cloud API webhook payload."""
    entry = (payload.get("entry") or [{}])[0]
    changes = (entry.get("changes") or [{}])[0]
    value = changes.get("value", {})
    messages = value.get("messages", [])
    contacts = value.get("contacts", [])

    msg = messages[0] if messages else {}
    contact = contacts[0] if contacts else {}

    text = ""
    msg_type = msg.get("type", "")
    if msg_type == "text":
        text = (msg.get("text") or {}).get("body", "")
    elif msg_type == "image":
        text = (msg.get("image") or {}).get("caption", "[image]")
    elif msg_type == "document":
        text = (msg.get("document") or {}).get("caption", "[document]")
    elif msg_type == "video":
        text = (msg.get("video") or {}).get("caption", "[video]")
    elif msg_type == "audio":
        text = "[audio]"
    elif msg_type == "location":
        loc = msg.get("location", {})
        text = f"[location: {loc.get('latitude')},{loc.get('longitude')}]"
    elif msg_type == "reaction":
        text = (msg.get("reaction") or {}).get("emoji", "")

    attachments: list[dict[str, Any]] = []
    for media_key in ("image", "document", "video", "audio", "sticker"):
        media = msg.get(media_key)
        if isinstance(media, dict) and media.get("id"):
            attachments.append({
                "type": media_key,
                "media_id": media.get("id"),
                "mime_type": media.get("mime_type", ""),
            })

    sender = msg.get("from", "")
    profile_name = (contact.get("profile") or {}).get("name", "")

    return NormalizedMessage(
        channel_type="whatsapp",
        channel_id=value.get("metadata", {}).get("phone_number_id", ""),
        peer_id=sender,
        message_id=msg.get("id", ""),
        user_id=sender,
        text=text,
        attachments=attachments,
        source_type="chat",
        raw=payload,
        extra={
            "profile_name": profile_name,
            "message_type": msg_type,
            "phone_number_id": value.get("metadata", {}).get("phone_number_id", ""),
        },
    )


def _extract_baileys(payload: dict[str, Any]) -> NormalizedMessage:
    """Normalise a Baileys-style WhatsApp event (forwarded from OpenClaw)."""
    key = payload.get("key", {})
    msg = payload.get("message", {})

    text = (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or (msg.get("imageMessage") or {}).get("caption")
        or ""
    )

    return NormalizedMessage(
        channel_type="whatsapp",
        channel_id=key.get("remoteJid", ""),
        peer_id=key.get("participant") or key.get("remoteJid", ""),
        message_id=key.get("id", ""),
        text=text,
        source_type="chat",
        raw=payload,
        extra={"format": "baileys"},
    )


class WhatsAppAdapter(BaseChannelAdapter):
    """Adapter for WhatsApp webhooks (Cloud API and Baileys)."""

    @property
    def channel_type(self) -> str:
        return "whatsapp"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        if "entry" in payload:
            return _extract_cloud_api(payload)
        if "key" in payload and "message" in payload:
            return _extract_baileys(payload)
        return _extract_cloud_api(payload)
