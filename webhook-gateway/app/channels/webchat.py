"""WebChat channel adapter.

Handles messages from browser-based WebChat UIs that POST JSON directly
to the gateway.  Also serves as the adapter for OpenClaw's built-in
WebChat component.
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class WebChatAdapter(BaseChannelAdapter):
    """Adapter for WebChat / browser-based chat payloads."""

    @property
    def channel_type(self) -> str:
        return "webchat"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        text = (
            payload.get("text")
            or payload.get("message")
            or payload.get("content")
            or ""
        )

        attachments: list[dict[str, Any]] = []
        for att in payload.get("attachments", []):
            if isinstance(att, dict):
                attachments.append({
                    "filename": att.get("filename") or att.get("name", ""),
                    "mime_type": att.get("contentType") or att.get("mime_type", ""),
                    "url": att.get("url", ""),
                })

        return NormalizedMessage(
            channel_type="webchat",
            channel_id=payload.get("channel_id") or payload.get("session_id", ""),
            peer_id=payload.get("user_id") or payload.get("sender", ""),
            message_id=payload.get("message_id") or payload.get("id", ""),
            user_id=payload.get("user_id"),
            text=text,
            attachments=attachments,
            source_type="chat",
            raw=payload,
            extra={
                "session_id": payload.get("session_id", ""),
                "locale": payload.get("locale", ""),
            },
        )
