"""Unit tests for channel adapters."""

from __future__ import annotations

import pytest

from app.channels.email import EmailAdapter
from app.channels.generic import GenericAdapter
from app.channels.video import VideoAdapter


# ---------------------------------------------------------------------------
# Generic adapter
# ---------------------------------------------------------------------------

class TestGenericAdapter:
    @pytest.fixture()
    def adapter(self):
        return GenericAdapter()

    @pytest.mark.asyncio
    async def test_normalize_minimal(self, adapter):
        msg = await adapter.normalize({"text": "hello"})
        assert msg.channel_type == "generic"
        assert msg.text == "hello"

    @pytest.mark.asyncio
    async def test_normalize_extracts_ids(self, adapter):
        msg = await adapter.normalize({
            "user_id": "u1",
            "channel_id": "c1",
            "peer_id": "p1",
            "thread_id": "t1",
            "message_id": "m1",
            "body": "payload body",
            "source_type": "chat",
        })
        assert msg.user_id == "u1"
        assert msg.channel_id == "c1"
        assert msg.peer_id == "p1"
        assert msg.thread_id == "t1"
        assert msg.message_id == "m1"
        assert msg.text == "payload body"
        assert msg.source_type == "chat"

    @pytest.mark.asyncio
    async def test_normalize_empty_payload(self, adapter):
        msg = await adapter.normalize({})
        assert msg.channel_type == "generic"
        assert msg.text is None

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "generic"


# ---------------------------------------------------------------------------
# Email adapter
# ---------------------------------------------------------------------------

class TestEmailAdapter:
    @pytest.fixture()
    def adapter(self):
        return EmailAdapter()

    @pytest.mark.asyncio
    async def test_sendgrid_format(self, adapter):
        payload = {
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Test Subject",
            "text": "Plain text body",
            "html": "<p>HTML body</p>",
            "attachment-info": {
                "attachment1": {"filename": "doc.pdf", "type": "application/pdf"},
            },
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "email"
        assert msg.peer_id == "sender@example.com"
        assert msg.channel_id == "recipient@example.com"
        assert msg.subject == "Test Subject"
        assert msg.text == "Plain text body"
        assert msg.html == "<p>HTML body</p>"
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["filename"] == "doc.pdf"
        assert msg.source_type == "email"

    @pytest.mark.asyncio
    async def test_mailgun_format(self, adapter):
        payload = {
            "signature": {"token": "abc"},
            "event-data": {
                "sender": "mg-sender@example.com",
                "recipient": "mg-recipient@example.com",
                "message": {
                    "headers": {
                        "from": "mg-sender@example.com",
                        "to": "mg-recipient@example.com",
                        "subject": "MG Subject",
                        "message-id": "mg-123",
                    },
                    "body": {"text": "Mailgun body", "html": "<b>MG</b>"},
                },
            },
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "email"
        assert msg.peer_id == "mg-sender@example.com"
        assert msg.subject == "MG Subject"
        assert msg.text == "Mailgun body"

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "email"


# ---------------------------------------------------------------------------
# Video adapter
# ---------------------------------------------------------------------------

class TestVideoAdapter:
    @pytest.fixture()
    def adapter(self):
        return VideoAdapter()

    @pytest.mark.asyncio
    async def test_zoom_format(self, adapter):
        payload = {
            "event": "meeting.ended",
            "payload": {
                "object": {
                    "id": 12345,
                    "uuid": "zoom-uuid",
                    "host_id": "host-1",
                    "topic": "Weekly Standup",
                    "participant": [
                        {"user_name": "Alice"},
                        {"email": "bob@example.com"},
                    ],
                    "recording_files": [
                        {
                            "recording_type": "shared_screen_with_speaker_view",
                            "download_url": "https://zoom.us/rec/123",
                        },
                    ],
                },
            },
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "video"
        assert msg.source_type == "conferencing"
        assert "Weekly Standup" in msg.text
        assert msg.recording_url == "https://zoom.us/rec/123"
        assert "Alice" in msg.participants
        assert msg.extra["provider"] == "zoom"

    @pytest.mark.asyncio
    async def test_google_meet_format(self, adapter):
        payload = {
            "eventData": {
                "summary": "Design Review",
                "attendees": [
                    {"email": "alice@example.com"},
                    {"email": "bob@example.com"},
                ],
                "conferenceData": {
                    "conferenceId": "meet-123",
                    "entryPoints": [
                        {"entryPointType": "video", "uri": "https://meet.google.com/abc"},
                    ],
                },
            },
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "video"
        assert msg.source_type == "conferencing"
        assert "Design Review" in msg.text
        assert msg.extra["provider"] == "google_meet"
        assert "alice@example.com" in msg.participants

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "video"
