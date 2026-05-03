"""Video conferencing channel adapter.

Supports Zoom and Google Meet webhook event formats.  Extracts meeting
metadata, participant lists, recording URLs, and transcript content.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage

_log = logging.getLogger("openclaw_gateway.channels.video")


def _extract_zoom(payload: dict[str, Any]) -> NormalizedMessage:
    """Normalise a Zoom webhook event payload."""
    event = payload.get("event", "")
    pl = payload.get("payload", {})
    obj = pl.get("object", {})

    participants = [
        p.get("user_name") or p.get("email", "")
        for p in obj.get("participant", obj.get("participants", []))
        if isinstance(p, dict)
    ]

    recording_files = obj.get("recording_files", [])
    recording_url = None
    transcript_url = None
    for rf in recording_files:
        if isinstance(rf, dict):
            if rf.get("recording_type") == "shared_screen_with_speaker_view":
                recording_url = rf.get("download_url") or rf.get("play_url")
            if rf.get("file_type") == "TRANSCRIPT":
                transcript_url = rf.get("download_url")

    text_parts = [f"Zoom event: {event}"]
    if obj.get("topic"):
        text_parts.append(f"Topic: {obj['topic']}")
    if transcript_url:
        text_parts.append(f"Transcript: {transcript_url}")

    return NormalizedMessage(
        channel_type="video",
        channel_id=str(obj.get("id", "")),
        message_id=str(obj.get("uuid", "")),
        user_id=str(obj.get("host_id", "")),
        text="\n".join(text_parts),
        participants=participants,
        recording_url=recording_url or transcript_url,
        source_type="conferencing",
        raw=payload,
        extra={"provider": "zoom", "event": event},
    )


def _extract_google_meet(payload: dict[str, Any]) -> NormalizedMessage:
    """Normalise a Google Meet / Calendar API webhook payload."""
    event_data = payload.get("eventData") or payload.get("event_data") or payload
    conference = event_data.get("conferenceData") or event_data.get("conference_data") or {}
    entry_points = conference.get("entryPoints", conference.get("entry_points", []))
    attendees = event_data.get("attendees", [])

    meeting_url = ""
    for ep in entry_points:
        if isinstance(ep, dict) and ep.get("entryPointType") == "video":
            meeting_url = ep.get("uri", "")
            break

    participants = [
        a.get("email", "") for a in attendees if isinstance(a, dict)
    ]

    summary = event_data.get("summary", event_data.get("title", "Google Meet"))

    return NormalizedMessage(
        channel_type="video",
        channel_id=conference.get("conferenceId", conference.get("conference_id", "")),
        text=f"Google Meet: {summary}",
        participants=participants,
        recording_url=meeting_url,
        source_type="conferencing",
        raw=payload,
        extra={"provider": "google_meet"},
    )


class VideoAdapter(BaseChannelAdapter):
    """Adapter for video conferencing webhooks (Zoom / Google Meet)."""

    @property
    def channel_type(self) -> str:
        return "video"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        if "event" in payload and "payload" in payload:
            _log.debug("Detected Zoom format")
            return _extract_zoom(payload)

        _log.debug("Using Google Meet format (default)")
        return _extract_google_meet(payload)
