"""PagerDuty webhook channel adapter.

Handles PagerDuty V3 webhook payloads for incident events.

Reference: https://developer.pagerduty.com/docs/webhooks/v3-overview/
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class PagerDutyAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "pagerduty"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        event = payload.get("event", {})
        event_type = event.get("event_type", "")
        data = event.get("data", {})

        incident_number = data.get("number", "")
        title = data.get("title", "")
        status = data.get("status", "")
        urgency = data.get("urgency", "")
        priority = data.get("priority", {})
        priority_name = priority.get("summary", "") if isinstance(priority, dict) else ""
        service = data.get("service", {})
        service_name = service.get("summary", "") if isinstance(service, dict) else ""
        assignees = data.get("assignees", [])
        assignee_names = [a.get("summary", "") for a in assignees if isinstance(a, dict)]
        html_url = data.get("html_url", "")

        text_parts = [f"PagerDuty: {event_type}"]
        text_parts.append(f"Incident #{incident_number}: {title}")
        if status:
            text_parts.append(f"Status: {status}")
        if urgency:
            text_parts.append(f"Urgency: {urgency}")
        if priority_name:
            text_parts.append(f"Priority: {priority_name}")
        if service_name:
            text_parts.append(f"Service: {service_name}")
        if assignee_names:
            text_parts.append(f"Assigned to: {', '.join(assignee_names)}")

        # Resolve/acknowledge details
        resolved_by = data.get("resolved_by", {})
        if isinstance(resolved_by, dict) and resolved_by.get("summary"):
            text_parts.append(f"Resolved by: {resolved_by['summary']}")

        # Log entries
        log_entries = data.get("log_entries", [])
        for entry in log_entries[:3]:
            if isinstance(entry, dict):
                channel = entry.get("channel", {})
                summary = channel.get("summary", "") if isinstance(channel, dict) else ""
                if summary:
                    text_parts.append(f"Note: {summary}")

        return NormalizedMessage(
            channel_type="pagerduty",
            channel_id=service_name,
            message_id=data.get("id", ""),
            user_id=assignee_names[0] if assignee_names else "",
            text="\n".join(text_parts),
            source_type="infrastructure",
            raw=payload,
            extra={
                "event_type": event_type,
                "incident_number": incident_number,
                "status": status,
                "urgency": urgency,
                "service": service_name,
                "url": html_url,
            },
        )
