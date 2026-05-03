"""Notion webhook channel adapter.

Handles Notion webhook payloads for page and database change events.

Reference: https://developers.notion.com/docs/webhooks
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class NotionAdapter(BaseChannelAdapter):
    """Adapter for Notion webhook payloads."""

    @property
    def channel_type(self) -> str:
        return "notion"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        event_type = payload.get("type", "")
        data = payload.get("data", payload)

        # Page events
        page = data.get("page", data.get("object", {}))
        page_id = page.get("id", "")
        parent = page.get("parent", {})

        # Extract title from properties
        title = ""
        properties = page.get("properties", {})
        for prop in properties.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title_parts = prop.get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_parts if isinstance(t, dict))
                break

        if not title:
            title = page.get("title", "")
            if isinstance(title, list):
                title = "".join(t.get("plain_text", "") for t in title if isinstance(t, dict))

        # Build text
        text_parts = [f"Notion: {event_type}"]
        if title:
            text_parts.append(f"Page: {title}")

        # Database info
        database = data.get("database", {})
        db_title = ""
        if database:
            db_title_parts = database.get("title", [])
            if isinstance(db_title_parts, list):
                db_title = "".join(t.get("plain_text", "") for t in db_title_parts if isinstance(t, dict))
            text_parts.append(f"Database: {db_title}")

        # Page content (if included)
        content = data.get("content", "")
        if content:
            text_parts.append(f"\n{content[:2000]}")

        # URL
        url = page.get("url", "")

        # User
        user = data.get("user", page.get("last_edited_by", {}))
        user_name = user.get("name", user.get("id", ""))

        return NormalizedMessage(
            channel_type="notion",
            channel_id=parent.get("database_id", parent.get("page_id", "")),
            peer_id=user_name,
            message_id=page_id,
            user_id=user.get("id", user_name),
            text="\n".join(text_parts),
            source_type="document",
            raw=payload,
            extra={
                "event_type": event_type,
                "page_id": page_id,
                "title": title,
                "url": url,
                "database_title": db_title,
            },
        )
