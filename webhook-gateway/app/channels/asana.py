"""Asana webhook channel adapter.

Handles Asana webhook payloads for task, project, and story events.

Reference: https://developers.asana.com/docs/webhooks-guide
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class AsanaAdapter(BaseChannelAdapter):

    @property
    def channel_type(self) -> str:
        return "asana"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        # Asana sends events array
        events = payload.get("events", [payload])
        event = events[0] if events else {}

        resource = event.get("resource", {})
        parent = event.get("parent", {})
        user = event.get("user", {})
        action = event.get("action", "")
        resource_type = resource.get("resource_type", "")

        text_parts = [f"Asana: {resource_type} {action}"]

        # Task
        if resource_type == "task":
            name = resource.get("name", "")
            if name:
                text_parts.append(f"Task: {name}")

        # Story (comment/activity)
        elif resource_type == "story":
            story_text = resource.get("text", "")
            story_type = resource.get("resource_subtype", "")
            if story_text:
                text_parts.append(f"{story_type}: {story_text[:1000]}")

        # Project
        elif resource_type == "project":
            name = resource.get("name", "")
            if name:
                text_parts.append(f"Project: {name}")

        # Parent context
        if parent:
            parent_name = parent.get("name", "")
            parent_type = parent.get("resource_type", "")
            if parent_name:
                text_parts.append(f"In {parent_type}: {parent_name}")

        # User
        user_name = user.get("name", user.get("gid", ""))

        # Batch
        if len(events) > 1:
            text_parts.append(f"\n{len(events)} events in batch")

        return NormalizedMessage(
            channel_type="asana",
            channel_id=parent.get("gid", ""),
            peer_id=user_name,
            message_id=resource.get("gid", ""),
            user_id=user.get("gid", user_name),
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource.get("gid", ""),
            },
        )
