"""Twilio webhook channel adapter.

Handles Twilio SMS/WhatsApp webhook payloads. Twilio sends form-encoded
POST requests for incoming messages.

Reference: https://www.twilio.com/docs/messaging/guides/webhook-request
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class TwilioAdapter(BaseChannelAdapter):
    """Adapter for Twilio SMS and WhatsApp webhook payloads."""

    @property
    def channel_type(self) -> str:
        return "twilio"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        # Twilio sends form-encoded data, FastAPI parses it into a dict
        from_number = payload.get("From", "")
        to_number = payload.get("To", "")
        body = payload.get("Body", "")
        message_sid = payload.get("MessageSid", "")
        account_sid = payload.get("AccountSid", "")
        num_media = int(payload.get("NumMedia", "0") or "0")

        # Determine if SMS or WhatsApp
        is_whatsapp = from_number.startswith("whatsapp:")
        channel = "whatsapp" if is_whatsapp else "sms"
        clean_from = from_number.replace("whatsapp:", "")
        clean_to = to_number.replace("whatsapp:", "")

        text_parts = []
        if body:
            text_parts.append(body)

        # Collect media attachments
        attachments: list[dict[str, Any]] = []
        for i in range(num_media):
            media_url = payload.get(f"MediaUrl{i}", "")
            media_type = payload.get(f"MediaContentType{i}", "")
            if media_url:
                attachments.append({
                    "url": media_url,
                    "mime_type": media_type,
                    "filename": f"media_{i}.{_ext_from_mime(media_type)}",
                })

        if not text_parts and attachments:
            text_parts.append(f"[{len(attachments)} media attachment(s)]")

        return NormalizedMessage(
            channel_type="twilio",
            channel_id=clean_to,
            peer_id=clean_from,
            message_id=message_sid,
            user_id=clean_from,
            text="\n".join(text_parts),
            attachments=attachments,
            source_type="chat",
            raw=payload,
            extra={
                "channel": channel,
                "account_sid": account_sid,
                "from": clean_from,
                "to": clean_to,
                "num_media": num_media,
                "sms_status": payload.get("SmsStatus", ""),
            },
        )


def _ext_from_mime(mime: str) -> str:
    """Get file extension from MIME type."""
    mapping = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "video/mp4": "mp4",
        "audio/ogg": "ogg",
        "audio/mpeg": "mp3",
        "application/pdf": "pdf",
    }
    return mapping.get(mime, "bin")
