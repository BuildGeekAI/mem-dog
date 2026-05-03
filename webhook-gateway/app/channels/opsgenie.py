"""OpsGenie webhook channel adapter.

Handles OpsGenie alert webhook payloads.

Reference: https://support.atlassian.com/opsgenie/docs/integrate-opsgenie-with-webhook/
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class OpsGenieAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "opsgenie"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        action = payload.get("action", "")
        alert = payload.get("alert", {})

        alert_id = alert.get("alertId", "")
        message = alert.get("message", "")
        priority = alert.get("priority", "")
        source = alert.get("source", "")
        tags = alert.get("tags", [])
        teams = alert.get("teams", [])
        description = alert.get("description", "")
        username = alert.get("username", payload.get("source", {}).get("name", ""))

        text_parts = [f"OpsGenie: {action}"]
        if message:
            text_parts.append(f"Alert: {message}")
        if priority:
            text_parts.append(f"Priority: {priority}")
        if source:
            text_parts.append(f"Source: {source}")
        if tags:
            text_parts.append(f"Tags: {', '.join(str(t) for t in tags)}")
        if teams:
            team_names = [t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in teams]
            text_parts.append(f"Teams: {', '.join(team_names)}")
        if description:
            text_parts.append(f"\n{description[:1000]}")

        return NormalizedMessage(
            channel_type="opsgenie",
            channel_id=source,
            peer_id=username,
            message_id=alert_id,
            text="\n".join(text_parts),
            source_type="infrastructure",
            raw=payload,
            extra={
                "action": action,
                "priority": priority,
                "source": source,
                "tags": tags,
            },
        )
