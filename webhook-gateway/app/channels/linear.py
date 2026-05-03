"""Linear webhook channel adapter.

Handles Linear webhook payloads for issue, comment, project,
and cycle events.

Reference: https://developers.linear.app/docs/graphql/webhooks
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


_ACTION_LABELS = {
    "create": "Created",
    "update": "Updated",
    "remove": "Removed",
}


class LinearAdapter(BaseChannelAdapter):
    """Adapter for Linear webhook payloads."""

    @property
    def channel_type(self) -> str:
        return "linear"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        action = payload.get("action", "")
        event_type = payload.get("type", "")
        data = payload.get("data", {})
        url = payload.get("url", data.get("url", ""))

        action_label = _ACTION_LABELS.get(action, action)
        text_parts = [f"Linear: {event_type} {action_label}"]

        # Issue
        if event_type == "Issue":
            identifier = data.get("identifier", "")
            title = data.get("title", "")
            description = data.get("description", "")
            state = data.get("state", {})
            state_name = state.get("name", "") if isinstance(state, dict) else str(state)
            priority_label = data.get("priorityLabel", "")
            assignee = data.get("assignee", {})
            assignee_name = assignee.get("name", "") if isinstance(assignee, dict) else ""
            team = data.get("team", {})
            team_name = team.get("name", "") if isinstance(team, dict) else ""
            labels = data.get("labels", [])
            label_names = [l.get("name", "") for l in labels if isinstance(l, dict)]

            text_parts.append(f"Issue: {identifier} — {title}")
            if state_name:
                text_parts.append(f"Status: {state_name}")
            if priority_label:
                text_parts.append(f"Priority: {priority_label}")
            if assignee_name:
                text_parts.append(f"Assignee: {assignee_name}")
            if team_name:
                text_parts.append(f"Team: {team_name}")
            if label_names:
                text_parts.append(f"Labels: {', '.join(label_names)}")
            if description and action == "create":
                text_parts.append(f"\n{description[:1000]}")

        # Comment
        elif event_type == "Comment":
            body = data.get("body", "")
            issue = data.get("issue", {})
            issue_id = issue.get("identifier", "") if isinstance(issue, dict) else ""
            issue_title = issue.get("title", "") if isinstance(issue, dict) else ""
            user = data.get("user", {})
            user_name = user.get("name", "") if isinstance(user, dict) else ""

            text_parts.append(f"On {issue_id}: {issue_title}")
            text_parts.append(f"By {user_name}:")
            text_parts.append(body[:1000])

        # Project
        elif event_type == "Project":
            name = data.get("name", "")
            description = data.get("description", "")
            state = data.get("state", "")
            text_parts.append(f"Project: {name}")
            if state:
                text_parts.append(f"State: {state}")
            if description:
                text_parts.append(description[:500])

        # Cycle
        elif event_type == "Cycle":
            number = data.get("number", "")
            name = data.get("name", "")
            text_parts.append(f"Cycle #{number}: {name}")

        # Fallback
        else:
            title = data.get("title", data.get("name", ""))
            if title:
                text_parts.append(title)

        # Actor
        creator = data.get("creator", data.get("user", {}))
        creator_name = creator.get("name", "") if isinstance(creator, dict) else ""

        return NormalizedMessage(
            channel_type="linear",
            channel_id=data.get("teamId", data.get("team", {}).get("id", "") if isinstance(data.get("team"), dict) else ""),
            peer_id=creator_name,
            message_id=data.get("id", ""),
            user_id=creator.get("id", creator_name) if isinstance(creator, dict) else creator_name,
            text="\n".join(text_parts),
            source_type="other",
            raw=payload,
            extra={
                "event_type": event_type,
                "action": action,
                "url": url,
            },
        )
