"""Sentry webhook channel adapter.

Handles Sentry webhook payloads for error, issue, and alert events.

Reference: https://docs.sentry.io/organization/integrations/integration-platform/webhooks/
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class SentryAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "sentry"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        action = payload.get("action", "")
        data = payload.get("data", {})
        actor = payload.get("actor", {})

        # Issue/error event
        issue = data.get("issue", data.get("event", {}))
        title = issue.get("title", "")
        culprit = issue.get("culprit", "")
        level = issue.get("level", "")
        platform = issue.get("platform", "")
        project = issue.get("project", {})
        project_name = project.get("name", project.get("slug", "")) if isinstance(project, dict) else ""
        url = issue.get("web_url", issue.get("url", ""))
        count = issue.get("count", "")

        # Error message / stacktrace
        metadata = issue.get("metadata", {})
        error_type = metadata.get("type", "") if isinstance(metadata, dict) else ""
        error_value = metadata.get("value", "") if isinstance(metadata, dict) else ""

        text_parts = [f"Sentry: {action}"]
        if title:
            text_parts.append(f"Error: {title}")
        if error_type and error_value:
            text_parts.append(f"{error_type}: {error_value}")
        if culprit:
            text_parts.append(f"In: {culprit}")
        if level:
            text_parts.append(f"Level: {level}")
        if platform:
            text_parts.append(f"Platform: {platform}")
        if project_name:
            text_parts.append(f"Project: {project_name}")
        if count:
            text_parts.append(f"Occurrences: {count}")

        # Tags
        tags = issue.get("tags", [])
        tag_pairs = []
        for t in tags[:5]:
            if isinstance(t, dict):
                tag_pairs.append(f"{t.get('key', '')}={t.get('value', '')}")
        if tag_pairs:
            text_parts.append(f"Tags: {', '.join(tag_pairs)}")

        # Alert rule (for alert events)
        alert = data.get("metric_alert", data.get("alert", {}))
        if isinstance(alert, dict) and alert.get("title"):
            text_parts.append(f"Alert: {alert['title']}")

        actor_name = actor.get("name", actor.get("email", "")) if isinstance(actor, dict) else ""

        return NormalizedMessage(
            channel_type="sentry",
            channel_id=project_name,
            peer_id=actor_name,
            message_id=str(issue.get("id", "")),
            text="\n".join(text_parts),
            source_type="infrastructure",
            raw=payload,
            extra={
                "action": action,
                "level": level,
                "platform": platform,
                "project": project_name,
                "url": url,
                "error_type": error_type,
            },
        )
