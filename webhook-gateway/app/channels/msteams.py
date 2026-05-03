"""Microsoft Teams channel adapter.

Handles Bot Framework ``Activity`` objects sent by the Teams connector
service.

Reference: https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-api-reference
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class MSTeamsAdapter(BaseChannelAdapter):
    """Adapter for Microsoft Teams Bot Framework activity payloads."""

    @property
    def channel_type(self) -> str:
        return "msteams"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        from_account = payload.get("from", {})
        conversation = payload.get("conversation", {})
        activity_type = payload.get("type", "")

        text = payload.get("text", "")
        attachments: list[dict[str, Any]] = []
        for att in payload.get("attachments", []):
            if isinstance(att, dict):
                attachments.append({
                    "mime_type": att.get("contentType", ""),
                    "url": att.get("contentUrl", ""),
                    "filename": att.get("name", ""),
                })

        return NormalizedMessage(
            channel_type="msteams",
            channel_id=conversation.get("id", ""),
            peer_id=from_account.get("id", ""),
            message_id=payload.get("id", ""),
            user_id=from_account.get("aadObjectId") or from_account.get("id", ""),
            text=text,
            attachments=attachments,
            source_type="chat",
            raw=payload,
            extra={
                "activity_type": activity_type,
                "tenant_id": (payload.get("channelData") or {}).get("tenant", {}).get("id", ""),
                "from_name": from_account.get("name", ""),
                "conversation_type": conversation.get("conversationType", ""),
            },
        )
