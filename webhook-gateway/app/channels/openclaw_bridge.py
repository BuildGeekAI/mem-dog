"""OpenClaw bridge adapter.

Accepts the normalised message format forwarded by an OpenClaw gateway
instance.  This covers all 25+ channels supported by OpenClaw (Signal,
Matrix, IRC, Google Chat, LINE, Feishu, Mattermost, Nextcloud Talk,
Nostr, Tlon, Twitch, Zalo, BlueBubbles/iMessage, Synology Chat, etc.)
that have already been normalised by the OpenClaw gateway before being
forwarded to this memdog OC-Gateway endpoint.

The OpenClaw gateway POSTs a JSON body with at minimum:
  - ``channel``: the originating channel type (e.g. ``"signal"``)
  - ``text``: message body
  - ``sender``: sender identifier
  - ``chatId``: chat/conversation identifier

Any additional fields are preserved in ``extra``.
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage

_SUPPORTED_OPENCLAW_CHANNELS = frozenset({
    "signal", "matrix", "irc", "googlechat", "line", "feishu",
    "mattermost", "nextcloud-talk", "nostr", "tlon", "twitch",
    "zalo", "zalouser", "bluebubbles", "imessage", "synology-chat",
})


class OpenClawBridgeAdapter(BaseChannelAdapter):
    """Adapter for messages forwarded by an OpenClaw gateway."""

    @property
    def channel_type(self) -> str:
        return "openclaw"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        channel = payload.get("channel") or payload.get("channelType") or "openclaw"
        sender = (
            payload.get("sender")
            or payload.get("from")
            or payload.get("userId")
            or ""
        )
        chat_id = (
            payload.get("chatId")
            or payload.get("chat_id")
            or payload.get("conversationId")
            or ""
        )
        text = (
            payload.get("text")
            or payload.get("body")
            or payload.get("message")
            or payload.get("content")
            or ""
        )

        attachments: list[dict[str, Any]] = []
        for att in payload.get("attachments", payload.get("media", [])):
            if isinstance(att, dict):
                attachments.append({
                    "filename": att.get("filename") or att.get("name", ""),
                    "mime_type": att.get("mimeType") or att.get("mime_type", ""),
                    "url": att.get("url", ""),
                })
            elif isinstance(att, str):
                attachments.append({"url": att})

        return NormalizedMessage(
            channel_type=channel,
            channel_id=chat_id,
            peer_id=sender,
            thread_id=payload.get("threadId") or payload.get("thread_id"),
            message_id=payload.get("messageId") or payload.get("message_id") or payload.get("id", ""),
            user_id=payload.get("userId") or payload.get("user_id"),
            text=text,
            attachments=attachments,
            source_type="chat",
            raw=payload,
            extra={
                "openclaw_channel": channel,
                "gateway_id": payload.get("gatewayId", ""),
                "agent_id": payload.get("agentId", ""),
            },
        )
