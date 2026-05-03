"""Telegram Bot API channel adapter.

Normalises Telegram Bot API ``Update`` objects (the JSON that Telegram
sends to a webhook URL configured via ``setWebhook``).

Reference: https://core.telegram.org/bots/api#update
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class TelegramAdapter(BaseChannelAdapter):
    """Adapter for Telegram Bot API webhook updates."""

    @property
    def channel_type(self) -> str:
        return "telegram"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        msg = (
            payload.get("message")
            or payload.get("edited_message")
            or payload.get("channel_post")
            or payload.get("edited_channel_post")
            or {}
        )
        chat = msg.get("chat", {})
        from_user = msg.get("from", {})

        text = msg.get("text") or msg.get("caption") or ""

        attachments: list[dict[str, Any]] = []
        for media_key in ("photo", "document", "video", "audio", "voice", "sticker"):
            media = msg.get(media_key)
            if media:
                item = media[-1] if isinstance(media, list) else media
                attachments.append({
                    "type": media_key,
                    "file_id": item.get("file_id", ""),
                    "file_unique_id": item.get("file_unique_id", ""),
                    "mime_type": item.get("mime_type", ""),
                    "filename": item.get("file_name", f"{media_key}.bin"),
                })

        return NormalizedMessage(
            channel_type="telegram",
            channel_id=str(chat.get("id", "")),
            peer_id=str(from_user.get("id", "")),
            thread_id=str(msg.get("message_thread_id", "")) or None,
            message_id=str(msg.get("message_id", "")),
            user_id=str(from_user.get("id", "")),
            text=text,
            attachments=attachments,
            source_type="chat",
            raw=payload,
            extra={
                "chat_type": chat.get("type", ""),
                "username": from_user.get("username", ""),
                "first_name": from_user.get("first_name", ""),
            },
        )
