"""Generic webhook channel adapter.

Accepts any JSON payload and passes it through with minimal normalisation.
This mirrors the behaviour of the existing Cloud Function webhook receiver.
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class GenericAdapter(BaseChannelAdapter):
    """Pass-through adapter for arbitrary JSON webhook payloads."""

    @property
    def channel_type(self) -> str:
        return "generic"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        text = (
            payload.get("text")
            or payload.get("body")
            or payload.get("message")
            or payload.get("content")
        )
        return NormalizedMessage(
            channel_type="generic",
            channel_id=payload.get("channel_id"),
            peer_id=payload.get("peer_id") or payload.get("sender_id"),
            thread_id=payload.get("thread_id"),
            message_id=payload.get("message_id") or payload.get("id"),
            user_id=payload.get("user_id") or payload.get("userId"),
            text=text,
            source_type=payload.get("source_type", "other"),
            raw=payload,
        )
