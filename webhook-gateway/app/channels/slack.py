"""Slack Events API channel adapter.

Handles Slack's ``event_callback`` payloads and the ``url_verification``
challenge handshake.

Reference: https://api.slack.com/events-api
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class SlackAdapter(BaseChannelAdapter):
    """Adapter for Slack Events API webhook payloads."""

    @property
    def channel_type(self) -> str:
        return "slack"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        if payload.get("type") == "url_verification":
            return NormalizedMessage(
                channel_type="slack",
                text="",
                source_type="chat",
                raw=payload,
                extra={"challenge": payload.get("challenge", "")},
            )

        event = payload.get("event", {})
        event_type = event.get("type", "")

        text = event.get("text", "")
        attachments: list[dict[str, Any]] = []
        for f in event.get("files", []):
            if isinstance(f, dict):
                attachments.append({
                    "filename": f.get("name", ""),
                    "mime_type": f.get("mimetype", ""),
                    "url": f.get("url_private", ""),
                })

        return NormalizedMessage(
            channel_type="slack",
            channel_id=event.get("channel", ""),
            peer_id=event.get("user", ""),
            thread_id=event.get("thread_ts"),
            message_id=event.get("ts", ""),
            user_id=event.get("user", ""),
            text=text,
            attachments=attachments,
            source_type="chat",
            raw=payload,
            extra={
                "event_type": event_type,
                "team_id": payload.get("team_id", ""),
                "subtype": event.get("subtype", ""),
            },
        )
