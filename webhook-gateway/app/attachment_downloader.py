"""Download channel attachments and ingest them into mem-dog.

Supports multiple download strategies per channel:
- **Slack**: Bearer token from Nango (url_private requires bot token)
- **Telegram**: Resolve file_id → download URL via Bot API, then fetch
- **WhatsApp**: Resolve media_id → download URL via Graph API, then fetch
- **MS Teams / Jira**: Bearer token from Nango (authenticated URLs)
- **Discord / Twilio / Webchat**: Public URLs, no auth needed
- **Email (SendGrid)**: Inline base64 content (no URL fetch needed)
- **Email (Mailgun)**: Temporary download URLs, no auth needed
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx

from . import config
from .credentials import get_credentials
from .forwarder import forward_envelope
from .envelope import build_envelope
from .channels.base import NormalizedMessage

_log = logging.getLogger("webhook_gateway.attachment_downloader")

_DOWNLOAD_TIMEOUT = 30.0
_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

NANGO_API_URL = config.NANGO_API_URL if hasattr(config, "NANGO_API_URL") else ""
NANGO_SECRET_KEY = config.NANGO_SECRET_KEY if hasattr(config, "NANGO_SECRET_KEY") else ""

# Telegram Bot API token — set via env or Nango
_TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# WhatsApp Cloud API — Graph API version
_WA_GRAPH_API_VERSION = "v21.0"


async def _get_nango_creds_direct(connection_id: str, provider_key: str) -> dict[str, Any] | None:
    """Fetch credentials from Nango by connection_id directly (not via end_user lookup)."""
    nango_url = NANGO_API_URL or os.getenv("NANGO_API_URL", "")
    nango_key = NANGO_SECRET_KEY or os.getenv("NANGO_SECRET_KEY", "")
    if not nango_url or not nango_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{nango_url}/connection/{connection_id}",
                params={"provider_config_key": provider_key},
                headers={"Authorization": f"Bearer {nango_key}"},
            )
            if resp.status_code == 200:
                creds = resp.json().get("credentials", {})
                return {
                    "access_token": creds.get("access_token", ""),
                    "token_type": creds.get("token_type", "bearer"),
                }
    except Exception as exc:
        _log.warning("Direct Nango credential fetch failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Channel-specific credential helpers
# ---------------------------------------------------------------------------

# Map channel types to their Nango provider keys
_CHANNEL_PROVIDER_MAP: dict[str, str] = {
    "slack": "slack",
    "msteams": "microsoft-teams",
    "jira": "jira",
}


async def _get_bearer_token(user_id: str, channel_type: str) -> str | None:
    """Get a Bearer token for channels that need authenticated downloads."""
    provider_key = _CHANNEL_PROVIDER_MAP.get(channel_type)
    if not provider_key:
        return None

    creds = await get_credentials(user_id, provider_key)
    if not creds or not creds.get("access_token"):
        # Fallback: connection_id = user_id
        creds = await _get_nango_creds_direct(user_id, provider_key)

    if creds and creds.get("access_token"):
        return creds["access_token"]

    _log.warning("No %s credentials for user %s", channel_type, user_id)
    return None


async def _resolve_telegram_url(file_id: str, user_id: str) -> str | None:
    """Resolve a Telegram file_id to a download URL via the Bot API.

    Uses TELEGRAM_BOT_TOKEN env var, or fetches from Nango if available.
    """
    bot_token = _TELEGRAM_BOT_TOKEN
    if not bot_token:
        # Try Nango for a telegram bot token
        creds = await get_credentials(user_id, "telegram")
        if creds:
            bot_token = creds.get("access_token") or creds.get("api_key") or ""
    if not bot_token:
        _log.warning("No Telegram bot token available, cannot resolve file_id %s", file_id)
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getFile",
                params={"file_id": file_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    file_path = data["result"]["file_path"]
                    return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    except Exception as exc:
        _log.warning("Telegram getFile failed for %s: %s", file_id, exc)
    return None


async def _resolve_whatsapp_url(media_id: str, user_id: str) -> tuple[str | None, dict[str, str]]:
    """Resolve a WhatsApp media_id to a download URL via the Graph API.

    Returns (url, headers) — WhatsApp media URLs require the same Bearer
    token for download.
    """
    creds = await get_credentials(user_id, "whatsapp-business")
    if not creds or not creds.get("access_token"):
        creds = await _get_nango_creds_direct(user_id, "whatsapp-business")

    token = creds.get("access_token", "") if creds else ""
    if not token:
        _log.warning("No WhatsApp credentials for user %s, cannot resolve media_id %s", user_id, media_id)
        return None, {}

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://graph.facebook.com/{_WA_GRAPH_API_VERSION}/{media_id}",
                headers=headers,
            )
            if resp.status_code == 200:
                url = resp.json().get("url")
                return url, headers
    except Exception as exc:
        _log.warning("WhatsApp media resolve failed for %s: %s", media_id, exc)
    return None, {}


# ---------------------------------------------------------------------------
# Main download + ingest logic
# ---------------------------------------------------------------------------

async def download_and_ingest_attachments(
    attachments: list[dict[str, Any]],
    channel_type: str,
    user_id: str,
    pipeline: str | None = None,
):
    """Download each attachment and forward through the pipeline."""
    for att in attachments:
        try:
            await _download_and_ingest_one(att, channel_type, user_id, pipeline)
        except Exception:
            _log.exception("Failed to download attachment: %s", att.get("filename", "?"))


async def _download_and_ingest_one(
    att: dict[str, Any],
    channel_type: str,
    user_id: str,
    pipeline: str | None,
):
    filename = att.get("filename") or att.get("name", "")
    url = att.get("url") or att.get("content_url", "")
    mime_type = att.get("mime_type") or att.get("content_type", "application/octet-stream")

    # --- Strategy 1: Inline base64 content (SendGrid email attachments) ---
    content_b64 = att.get("content_b64", "")
    if content_b64:
        content = base64.b64decode(content_b64)
        _log.info("Inline attachment %s (%d bytes, %s)", filename, len(content), mime_type)
        await _forward_content(content, filename, mime_type, channel_type, user_id, pipeline)
        return

    # --- Strategy 2: Telegram file_id resolution ---
    file_id = att.get("file_id", "")
    if file_id and not url and channel_type == "telegram":
        url = await _resolve_telegram_url(file_id, user_id)
        if not url:
            _log.warning("Could not resolve Telegram file_id %s for %s", file_id, filename)
            return

    # --- Strategy 3: WhatsApp media_id resolution ---
    media_id = att.get("media_id", "")
    if media_id and not url and channel_type == "whatsapp":
        resolved_url, wa_headers = await _resolve_whatsapp_url(media_id, user_id)
        if not resolved_url:
            _log.warning("Could not resolve WhatsApp media_id %s for %s", media_id, filename)
            return
        # WhatsApp media URLs need the same auth headers for download
        content = await _fetch_url(resolved_url, filename, wa_headers)
        if content:
            await _forward_content(content, filename, mime_type, channel_type, user_id, pipeline)
        return

    # --- Strategy 4: URL-based download (Slack, Discord, Jira, Teams, etc.) ---
    if not url:
        _log.debug("Attachment %s has no URL or resolvable ID, skipping", filename)
        return

    # Build auth headers for channels that need them
    headers: dict[str, str] = {}
    if channel_type in _CHANNEL_PROVIDER_MAP:
        token = await _get_bearer_token(user_id, channel_type)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif channel_type in ("slack", "msteams", "jira"):
            # These channels require auth — skip if no token
            _log.warning("No %s credentials for user %s, cannot download %s", channel_type, user_id, filename)
            return

    content = await _fetch_url(url, filename, headers)
    if content:
        await _forward_content(content, filename, mime_type, channel_type, user_id, pipeline)


async def _fetch_url(url: str, filename: str, headers: dict[str, str]) -> bytes | None:
    """Download a file from a URL. Returns bytes or None on failure."""
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT) as client:
        resp = await client.get(url, headers=headers, follow_redirects=True)
        if resp.status_code != 200:
            _log.warning("Download failed for %s: HTTP %s", filename, resp.status_code)
            return None

        content = resp.content
        if len(content) > _MAX_FILE_SIZE:
            _log.warning("Attachment %s too large (%d bytes), skipping", filename, len(content))
            return None

    _log.info("Downloaded attachment %s (%d bytes)", filename, len(content))
    return content


async def _forward_content(
    content: bytes,
    filename: str,
    mime_type: str,
    channel_type: str,
    user_id: str,
    pipeline: str | None,
):
    """Build an envelope for downloaded content and forward to the pipeline."""
    content_b64 = base64.b64encode(content).decode("ascii")
    msg = NormalizedMessage(
        channel_type=channel_type,
        text="",
        user_id=user_id,
        source_type="document",
        attachments=[],
        is_downloaded=True,
        raw={"attachment_data_b64": content_b64, "filename": filename},
    )

    envelope = build_envelope(
        msg,
        resolved_user_id=user_id,
        is_downloaded=True,
        mime_type=mime_type,
    )

    # Add file metadata to the envelope
    envelope["data"]["payload"]["filename"] = filename
    envelope["data"]["payload"]["size_bytes"] = len(content)
    envelope["data"]["payload"]["attachment_data_b64"] = content_b64

    await forward_envelope(envelope, pipeline=pipeline)
    _log.info("Ingested attachment %s for user %s via pipeline", filename, user_id)
