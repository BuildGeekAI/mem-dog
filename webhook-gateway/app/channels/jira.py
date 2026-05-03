"""Jira webhook channel adapter.

Normalizes Jira webhook payloads for issue events, comments, sprints,
and worklog updates into memdog's NormalizedMessage format.

Reference: https://developer.atlassian.com/server/jira/platform/webhooks/
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


# Map Jira webhook event names to human-readable labels
_EVENT_LABELS = {
    "jira:issue_created": "Issue Created",
    "jira:issue_updated": "Issue Updated",
    "jira:issue_deleted": "Issue Deleted",
    "comment_created": "Comment Added",
    "comment_updated": "Comment Updated",
    "comment_deleted": "Comment Deleted",
    "sprint_started": "Sprint Started",
    "sprint_closed": "Sprint Closed",
    "sprint_created": "Sprint Created",
    "sprint_updated": "Sprint Updated",
    "worklog_created": "Work Logged",
    "worklog_updated": "Work Log Updated",
    "issuelink_created": "Issues Linked",
    "issuelink_deleted": "Issue Link Removed",
    "attachment_created": "Attachment Added",
}


class JiraAdapter(BaseChannelAdapter):
    """Adapter for Jira webhook payloads."""

    @property
    def channel_type(self) -> str:
        return "jira"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        event = payload.get("webhookEvent", payload.get("event", ""))
        event_label = _EVENT_LABELS.get(event, event)

        issue = payload.get("issue", {})
        fields = issue.get("fields", {})
        comment = payload.get("comment", {})
        sprint = payload.get("sprint", {})
        user = payload.get("user", {})
        changelog = payload.get("changelog", {})

        # Build text summary
        text_parts = [f"Jira: {event_label}"]

        # Issue details
        issue_key = issue.get("key", "")
        summary = fields.get("summary", "")
        if issue_key:
            text_parts.append(f"Issue: {issue_key} — {summary}")

        status = fields.get("status", {}).get("name", "")
        priority = fields.get("priority", {}).get("name", "")
        issue_type = fields.get("issuetype", {}).get("name", "")
        assignee = fields.get("assignee", {})
        assignee_name = assignee.get("displayName", "") if assignee else ""
        reporter = fields.get("reporter", {})
        reporter_name = reporter.get("displayName", "") if reporter else ""
        project = fields.get("project", {})
        project_key = project.get("key", "")
        project_name = project.get("name", "")

        if issue_type:
            text_parts.append(f"Type: {issue_type}")
        if status:
            text_parts.append(f"Status: {status}")
        if priority:
            text_parts.append(f"Priority: {priority}")
        if assignee_name:
            text_parts.append(f"Assignee: {assignee_name}")
        if project_name:
            text_parts.append(f"Project: {project_name} ({project_key})")

        # Description
        description = fields.get("description", "")
        if description and "created" in event:
            text_parts.append(f"\n{description}")

        # Comment body
        if comment:
            comment_body = comment.get("body", "")
            comment_author = comment.get("author", {}).get("displayName", "")
            if comment_body:
                text_parts.append(f"\nComment by {comment_author}:\n{comment_body}")

        # Changelog (field changes)
        if changelog:
            items = changelog.get("items", [])
            for item in items[:5]:  # cap at 5 changes
                field_name = item.get("field", "")
                from_val = item.get("fromString", "")
                to_val = item.get("toString", "")
                text_parts.append(f"Changed {field_name}: {from_val} → {to_val}")

        # Sprint details
        if sprint:
            sprint_name = sprint.get("name", "")
            sprint_state = sprint.get("state", "")
            text_parts.append(f"Sprint: {sprint_name} ({sprint_state})")

        # Labels and components
        labels = fields.get("labels", [])
        components = [c.get("name", "") for c in fields.get("components", []) if isinstance(c, dict)]

        # Attachments
        attachments: list[dict[str, Any]] = []
        for att in fields.get("attachment", []):
            if isinstance(att, dict):
                attachments.append({
                    "filename": att.get("filename", ""),
                    "mime_type": att.get("mimeType", ""),
                    "url": att.get("content", ""),
                })

        # Actor
        actor_name = user.get("displayName", user.get("name", ""))

        return NormalizedMessage(
            channel_type="jira",
            channel_id=project_key,
            peer_id=actor_name,
            message_id=str(issue.get("id", "")),
            user_id=user.get("accountId", user.get("key", actor_name)),
            text="\n".join(text_parts),
            attachments=attachments,
            source_type="other",
            raw=payload,
            extra={
                "event": event,
                "issue_key": issue_key,
                "issue_type": issue_type,
                "status": status,
                "priority": priority,
                "assignee": assignee_name,
                "reporter": reporter_name,
                "project_key": project_key,
                "project_name": project_name,
                "labels": labels,
                "components": components,
            },
        )
