"""Datadog webhook channel adapter.

Handles Datadog webhook payloads for monitor alerts, events, and incidents.

Reference: https://docs.datadoghq.com/integrations/webhooks/
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class DatadogAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "datadog"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        # Datadog webhook format
        alert_type = payload.get("alert_type", "")
        title = payload.get("title", payload.get("event_title", ""))
        body = payload.get("body", payload.get("event_msg", ""))
        alert_status = payload.get("alert_status", payload.get("alert_transition", ""))
        hostname = payload.get("hostname", "")
        monitor_name = payload.get("monitor_name", payload.get("last_updated", ""))
        priority = payload.get("priority", "")
        tags = payload.get("tags", "")
        url = payload.get("url", payload.get("link", ""))
        org_name = payload.get("org", {}).get("name", "") if isinstance(payload.get("org"), dict) else ""
        snapshot = payload.get("snapshot", "")

        text_parts = [f"Datadog: {alert_type or 'alert'}"]
        if title:
            text_parts.append(f"Title: {title}")
        if alert_status:
            text_parts.append(f"Status: {alert_status}")
        if hostname:
            text_parts.append(f"Host: {hostname}")
        if monitor_name:
            text_parts.append(f"Monitor: {monitor_name}")
        if priority:
            text_parts.append(f"Priority: {priority}")
        if tags:
            tag_str = tags if isinstance(tags, str) else ", ".join(tags)
            text_parts.append(f"Tags: {tag_str}")
        if body:
            text_parts.append(f"\n{str(body)[:1000]}")

        return NormalizedMessage(
            channel_type="datadog",
            channel_id=hostname,
            message_id=str(payload.get("id", payload.get("event_id", ""))),
            text="\n".join(text_parts),
            source_type="infrastructure",
            raw=payload,
            extra={
                "alert_type": alert_type,
                "alert_status": alert_status,
                "hostname": hostname,
                "priority": priority,
                "url": url,
                "snapshot": snapshot,
                "org": org_name,
            },
        )
