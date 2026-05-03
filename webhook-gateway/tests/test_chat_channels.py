"""Unit tests for chat channel adapters (Telegram, Slack, Discord,
WhatsApp, MS Teams, WebChat, OpenClaw bridge).
"""

from __future__ import annotations

import pytest

from app.channels.discord import DiscordAdapter
from app.channels.msteams import MSTeamsAdapter
from app.channels.openclaw_bridge import OpenClawBridgeAdapter
from app.channels.slack import SlackAdapter
from app.channels.telegram import TelegramAdapter
from app.channels.webchat import WebChatAdapter
from app.channels.whatsapp import WhatsAppAdapter


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

class TestTelegramAdapter:
    @pytest.fixture()
    def adapter(self):
        return TelegramAdapter()

    @pytest.mark.asyncio
    async def test_text_message(self, adapter):
        payload = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 111, "first_name": "Alice", "username": "alice"},
                "chat": {"id": 222, "type": "private"},
                "text": "Hello from Telegram",
            },
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "telegram"
        assert msg.text == "Hello from Telegram"
        assert msg.peer_id == "111"
        assert msg.channel_id == "222"
        assert msg.source_type == "chat"

    @pytest.mark.asyncio
    async def test_photo_message(self, adapter):
        payload = {
            "update_id": 2,
            "message": {
                "message_id": 43,
                "from": {"id": 111},
                "chat": {"id": 222, "type": "private"},
                "caption": "Check this out",
                "photo": [
                    {"file_id": "small", "width": 100},
                    {"file_id": "large", "width": 800},
                ],
            },
        }
        msg = await adapter.normalize(payload)
        assert msg.text == "Check this out"
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["file_id"] == "large"

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "telegram"


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

class TestSlackAdapter:
    @pytest.fixture()
    def adapter(self):
        return SlackAdapter()

    @pytest.mark.asyncio
    async def test_url_verification(self, adapter):
        payload = {"type": "url_verification", "challenge": "abc123"}
        msg = await adapter.normalize(payload)
        assert msg.extra["challenge"] == "abc123"

    @pytest.mark.asyncio
    async def test_message_event(self, adapter):
        payload = {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "user": "U456",
                "text": "Hello from Slack",
                "channel": "C789",
                "ts": "1234567890.000001",
            },
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "slack"
        assert msg.text == "Hello from Slack"
        assert msg.peer_id == "U456"
        assert msg.channel_id == "C789"
        assert msg.extra["team_id"] == "T123"

    @pytest.mark.asyncio
    async def test_message_with_files(self, adapter):
        payload = {
            "type": "event_callback",
            "event": {
                "type": "message",
                "user": "U1",
                "text": "See attached",
                "channel": "C1",
                "ts": "1.0",
                "files": [{"name": "doc.pdf", "mimetype": "application/pdf", "url_private": "https://files.slack.com/doc.pdf"}],
            },
        }
        msg = await adapter.normalize(payload)
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["filename"] == "doc.pdf"

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "slack"


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------

class TestDiscordAdapter:
    @pytest.fixture()
    def adapter(self):
        return DiscordAdapter()

    @pytest.mark.asyncio
    async def test_ping(self, adapter):
        msg = await adapter.normalize({"type": 1})
        assert msg.extra["interaction_type"] == "ping"

    @pytest.mark.asyncio
    async def test_message_event(self, adapter):
        payload = {
            "id": "msg-1",
            "content": "Hello from Discord",
            "channel_id": "ch-1",
            "guild_id": "g-1",
            "author": {"id": "u-1", "username": "alice"},
            "attachments": [{"filename": "img.png", "url": "https://cdn.discord.com/img.png", "content_type": "image/png"}],
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "discord"
        assert msg.text == "Hello from Discord"
        assert msg.peer_id == "u-1"
        assert len(msg.attachments) == 1
        assert msg.extra["guild_id"] == "g-1"

    @pytest.mark.asyncio
    async def test_slash_command(self, adapter):
        payload = {
            "type": 2,
            "id": "int-1",
            "channel_id": "ch-1",
            "guild_id": "g-1",
            "member": {"user": {"id": "u-2", "username": "bob"}},
            "data": {"name": "summarize"},
        }
        msg = await adapter.normalize(payload)
        assert msg.text == "summarize"
        assert msg.extra["command_name"] == "summarize"

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "discord"


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------

class TestWhatsAppAdapter:
    @pytest.fixture()
    def adapter(self):
        return WhatsAppAdapter()

    @pytest.mark.asyncio
    async def test_cloud_api_text(self, adapter):
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "pn-1"},
                        "contacts": [{"profile": {"name": "Alice"}}],
                        "messages": [{
                            "from": "+15551234567",
                            "id": "wamid.abc",
                            "type": "text",
                            "text": {"body": "Hello from WhatsApp"},
                        }],
                    },
                }],
            }],
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "whatsapp"
        assert msg.text == "Hello from WhatsApp"
        assert msg.peer_id == "+15551234567"
        assert msg.extra["profile_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_cloud_api_image(self, adapter):
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "pn-1"},
                        "contacts": [],
                        "messages": [{
                            "from": "+15551234567",
                            "id": "wamid.img",
                            "type": "image",
                            "image": {"id": "media-1", "mime_type": "image/jpeg", "caption": "Look!"},
                        }],
                    },
                }],
            }],
        }
        msg = await adapter.normalize(payload)
        assert msg.text == "Look!"
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["media_id"] == "media-1"

    @pytest.mark.asyncio
    async def test_baileys_format(self, adapter):
        payload = {
            "key": {"remoteJid": "123@s.whatsapp.net", "id": "baileys-1"},
            "message": {"conversation": "Hi from Baileys"},
        }
        msg = await adapter.normalize(payload)
        assert msg.text == "Hi from Baileys"
        assert msg.extra["format"] == "baileys"

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "whatsapp"


# ---------------------------------------------------------------------------
# MS Teams
# ---------------------------------------------------------------------------

class TestMSTeamsAdapter:
    @pytest.fixture()
    def adapter(self):
        return MSTeamsAdapter()

    @pytest.mark.asyncio
    async def test_message_activity(self, adapter):
        payload = {
            "type": "message",
            "id": "act-1",
            "from": {"id": "user-1", "name": "Alice", "aadObjectId": "aad-1"},
            "conversation": {"id": "conv-1", "conversationType": "personal"},
            "text": "Hello from Teams",
            "channelData": {"tenant": {"id": "tenant-1"}},
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "msteams"
        assert msg.text == "Hello from Teams"
        assert msg.user_id == "aad-1"
        assert msg.extra["tenant_id"] == "tenant-1"

    @pytest.mark.asyncio
    async def test_with_attachments(self, adapter):
        payload = {
            "type": "message",
            "id": "act-2",
            "from": {"id": "user-2"},
            "conversation": {"id": "conv-2"},
            "text": "See file",
            "attachments": [{"contentType": "application/pdf", "contentUrl": "https://teams.com/doc.pdf", "name": "doc.pdf"}],
        }
        msg = await adapter.normalize(payload)
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["name"] == "doc.pdf"

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "msteams"


# ---------------------------------------------------------------------------
# WebChat
# ---------------------------------------------------------------------------

class TestWebChatAdapter:
    @pytest.fixture()
    def adapter(self):
        return WebChatAdapter()

    @pytest.mark.asyncio
    async def test_basic_message(self, adapter):
        payload = {
            "text": "Hello from browser",
            "user_id": "web-user-1",
            "session_id": "sess-1",
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "webchat"
        assert msg.text == "Hello from browser"
        assert msg.user_id == "web-user-1"
        assert msg.extra["session_id"] == "sess-1"

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "webchat"


# ---------------------------------------------------------------------------
# OpenClaw Bridge
# ---------------------------------------------------------------------------

class TestOpenClawBridgeAdapter:
    @pytest.fixture()
    def adapter(self):
        return OpenClawBridgeAdapter()

    @pytest.mark.asyncio
    async def test_signal_message(self, adapter):
        payload = {
            "channel": "signal",
            "sender": "+15559876543",
            "chatId": "signal-chat-1",
            "text": "Hello from Signal",
            "messageId": "sig-msg-1",
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "signal"
        assert msg.text == "Hello from Signal"
        assert msg.peer_id == "+15559876543"
        assert msg.extra["openclaw_channel"] == "signal"

    @pytest.mark.asyncio
    async def test_matrix_message(self, adapter):
        payload = {
            "channel": "matrix",
            "sender": "@alice:matrix.org",
            "chatId": "!room:matrix.org",
            "text": "Hello from Matrix",
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "matrix"
        assert msg.text == "Hello from Matrix"

    @pytest.mark.asyncio
    async def test_irc_message(self, adapter):
        payload = {
            "channel": "irc",
            "sender": "alice",
            "chatId": "#general",
            "body": "Hello from IRC",
        }
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "irc"
        assert msg.text == "Hello from IRC"

    @pytest.mark.asyncio
    async def test_with_attachments(self, adapter):
        payload = {
            "channel": "googlechat",
            "sender": "user@corp.com",
            "chatId": "space-1",
            "text": "See file",
            "attachments": [{"name": "report.pdf", "mimeType": "application/pdf", "url": "https://chat.google.com/files/report.pdf"}],
        }
        msg = await adapter.normalize(payload)
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["filename"] == "report.pdf"

    @pytest.mark.asyncio
    async def test_unknown_channel_defaults(self, adapter):
        payload = {"text": "Hello", "sender": "someone"}
        msg = await adapter.normalize(payload)
        assert msg.channel_type == "openclaw"
        assert msg.text == "Hello"

    def test_channel_type(self, adapter):
        assert adapter.channel_type == "openclaw"
