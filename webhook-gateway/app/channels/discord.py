"""Discord channel adapter.

Handles Discord Interaction payloads (webhook-based) and the simplified
gateway event format used when a Discord bot forwards events via HTTP.

Reference: https://discord.com/developers/docs/interactions/receiving-and-responding
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage

# Discord interaction types
_PING = 1
_APPLICATION_COMMAND = 2
_MESSAGE_COMPONENT = 3


class DiscordAdapter(BaseChannelAdapter):
    """Adapter for Discord webhook / interaction payloads."""

    @property
    def channel_type(self) -> str:
        return "discord"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        int_type = payload.get("type")
        if int_type == _PING:
            return NormalizedMessage(
                channel_type="discord",
                text="",
                source_type="chat",
                raw=payload,
                extra={"interaction_type": "ping"},
            )

        if "author" in payload or "content" in payload:
            return self._from_message_event(payload)

        if "data" in payload and int_type in (_APPLICATION_COMMAND, _MESSAGE_COMPONENT):
            return self._from_interaction(payload)

        return self._from_message_event(payload)

    def _from_message_event(self, payload: dict[str, Any]) -> NormalizedMessage:
        author = payload.get("author", {})
        attachments = [
            {
                "filename": a.get("filename", ""),
                "url": a.get("url", ""),
                "mime_type": a.get("content_type", ""),
            }
            for a in payload.get("attachments", [])
            if isinstance(a, dict)
        ]

        return NormalizedMessage(
            channel_type="discord",
            channel_id=str(payload.get("channel_id", "")),
            peer_id=str(author.get("id", "")),
            message_id=str(payload.get("id", "")),
            user_id=str(author.get("id", "")),
            text=payload.get("content", ""),
            attachments=attachments,
            source_type="chat",
            raw=payload,
            extra={
                "guild_id": str(payload.get("guild_id", "")),
                "username": author.get("username", ""),
            },
        )

    def _from_interaction(self, payload: dict[str, Any]) -> NormalizedMessage:
        member = payload.get("member", {})
        user = member.get("user", {}) or payload.get("user", {})
        data = payload.get("data", {})

        return NormalizedMessage(
            channel_type="discord",
            channel_id=str(payload.get("channel_id", "")),
            peer_id=str(user.get("id", "")),
            message_id=str(payload.get("id", "")),
            user_id=str(user.get("id", "")),
            text=data.get("name", ""),
            source_type="chat",
            raw=payload,
            extra={
                "guild_id": str(payload.get("guild_id", "")),
                "interaction_type": str(payload.get("type", "")),
                "command_name": data.get("name", ""),
            },
        )
