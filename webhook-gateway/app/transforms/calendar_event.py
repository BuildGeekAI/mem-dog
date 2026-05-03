"""Calendar event transforms for unified calendar event model."""

from __future__ import annotations

from typing import Any

from . import register


def _base(raw: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    result = {
        "id": "",
        "title": "",
        "description": "",
        "start": None,
        "end": None,
        "attendees": [],
        "location": "",
        "organizer": "",
        "created_at": None,
        "raw": raw,
    }
    result.update({k: v for k, v in overrides.items() if v})
    return result


@register("google-calendar", "calendar_event")
def google_calendar_event(raw: dict[str, Any]) -> dict[str, Any]:
    start = raw.get("start", {})
    end = raw.get("end", {})
    attendees = raw.get("attendees", [])
    organizer = raw.get("organizer", {})
    return _base(
        raw,
        id=raw.get("id", ""),
        title=raw.get("summary", ""),
        description=raw.get("description", ""),
        start=start.get("dateTime") or start.get("date"),
        end=end.get("dateTime") or end.get("date"),
        attendees=[a.get("email", "") for a in attendees if a.get("email")],
        location=raw.get("location", ""),
        organizer=organizer.get("email", ""),
        created_at=raw.get("created"),
    )


@register("outlook", "calendar_event")
def outlook_calendar_event(raw: dict[str, Any]) -> dict[str, Any]:
    attendees = raw.get("attendees", [])
    organizer = raw.get("organizer", {})
    return _base(
        raw,
        id=raw.get("id", ""),
        title=raw.get("subject", ""),
        description=raw.get("bodyPreview", "") or (raw.get("body", {}).get("content", "")),
        start=raw.get("start", {}).get("dateTime"),
        end=raw.get("end", {}).get("dateTime"),
        attendees=[
            a.get("emailAddress", {}).get("address", "")
            for a in attendees if a.get("emailAddress")
        ],
        location=raw.get("location", {}).get("displayName", "") if isinstance(raw.get("location"), dict) else "",
        organizer=organizer.get("emailAddress", {}).get("address", ""),
        created_at=raw.get("createdDateTime"),
    )


@register("zoom", "calendar_event")
def zoom_calendar_event(raw: dict[str, Any]) -> dict[str, Any]:
    return _base(
        raw,
        id=str(raw.get("id", "")),
        title=raw.get("topic", ""),
        description=raw.get("agenda", ""),
        start=raw.get("start_time"),
        end=None,  # Zoom doesn't always provide end time directly
        attendees=[],
        location=raw.get("join_url", ""),
        organizer=raw.get("host_email", ""),
        created_at=raw.get("created_at"),
    )


@register("calendly", "calendar_event")
def calendly_calendar_event(raw: dict[str, Any]) -> dict[str, Any]:
    invitees = raw.get("invitees", [])
    location_data = raw.get("location", {})
    return _base(
        raw,
        id=raw.get("uri", ""),
        title=raw.get("name", ""),
        description="",
        start=raw.get("start_time"),
        end=raw.get("end_time"),
        attendees=[i.get("email", "") for i in invitees if i.get("email")],
        location=location_data.get("location", "") if isinstance(location_data, dict) else str(location_data),
        organizer=raw.get("event_memberships", [{}])[0].get("user_email", "") if raw.get("event_memberships") else "",
        created_at=raw.get("created_at"),
    )
