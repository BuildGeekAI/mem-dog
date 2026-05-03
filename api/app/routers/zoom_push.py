"""Zoom Webhook — auto-ingest meeting recordings and transcripts.

Zoom sends webhook events when recordings are completed. This router
receives them, downloads transcripts/recordings via Nango proxy, and
ingests into mem-dog.

Zoom webhook setup:
1. In marketplace.zoom.us → your app → Feature → Event Subscriptions
2. Add event: recording.completed
3. Set notification URL: https://<endpoint>/gke-api/api/v1/zoom/push
"""

import base64
import json
import logging
import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app import config
from app.nango_client import proxy_request
from app.models import (
    UniversalEnvelope,
    OriginDescriptor,
    PayloadDescriptor,
    ContextDescriptor,
    SourceType,
)
from app.routers.ingest import _forward_to_webhook, _store_direct

logger = logging.getLogger("mem_dog.routers.zoom_push")

router = APIRouter(prefix="/api/v1/zoom", tags=["Zoom"])

_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB for recordings

# Zoom connection mapping: user_id → connection_id
_ZOOM_FILE = "/data/zoom_connections.json"
_zoom_connections: dict[str, str] = {}
_zoom_loaded = False


def _load_zoom_connections() -> dict[str, str]:
    global _zoom_connections, _zoom_loaded
    if _zoom_loaded:
        return _zoom_connections
    try:
        if os.path.exists(_ZOOM_FILE):
            with open(_ZOOM_FILE) as f:
                _zoom_connections = json.load(f)
    except Exception:
        pass
    _zoom_loaded = True
    return _zoom_connections


def _save_zoom_connections():
    try:
        os.makedirs(os.path.dirname(_ZOOM_FILE), exist_ok=True)
        with open(_ZOOM_FILE, "w") as f:
            json.dump(_zoom_connections, f)
    except Exception:
        logger.warning("Failed to persist zoom connections")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ZoomRegisterRequest(BaseModel):
    connection_id: str
    user_id: str = ""


# ---------------------------------------------------------------------------
# Webhook receiver (called by Zoom, no auth)
# ---------------------------------------------------------------------------

@router.post("/push")
async def zoom_push(request: Request, background_tasks: BackgroundTasks):
    """Receive Zoom webhook event.

    Handles:
    - endpoint.url_validation (challenge-response)
    - recording.completed (download + ingest)
    - recording.transcript_completed (download transcript + ingest)
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid body"}

    event = body.get("event", "")

    # Zoom URL validation challenge
    if event == "endpoint.url_validation":
        import hashlib
        import hmac
        plain_token = body.get("payload", {}).get("plainToken", "")
        secret = os.getenv("ZOOM_WEBHOOK_SECRET", "")
        if plain_token and secret:
            hash_obj = hmac.new(secret.encode(), plain_token.encode(), hashlib.sha256)
            return {
                "plainToken": plain_token,
                "encryptedToken": hash_obj.hexdigest(),
            }
        return {"plainToken": plain_token, "encryptedToken": ""}

    if event not in ("recording.completed", "recording.transcript_completed"):
        logger.debug("Ignoring Zoom event: %s", event)
        return {"status": "ignored", "event": event}

    logger.info("Zoom webhook: %s", event)

    background_tasks.add_task(_process_zoom_recording, body=body)
    return {"status": "ok"}


async def _process_zoom_recording(body: dict):
    """Download recording files/transcripts and ingest them."""
    payload = body.get("payload", {})
    obj = payload.get("object", {})
    topic = obj.get("topic", "Zoom Meeting")
    host_id = str(obj.get("host_id", ""))
    host_email = str(obj.get("host_email", ""))
    meeting_id = str(obj.get("id", ""))
    start_time = obj.get("start_time", "")
    duration = obj.get("duration", 0)
    participants = [
        p.get("user_name") or p.get("email", "")
        for p in obj.get("participant", obj.get("participants", []))
        if isinstance(p, dict)
    ]

    recording_files = obj.get("recording_files", [])
    # Zoom includes a download_token for direct file access (no OAuth needed)
    download_token = body.get("download_token", payload.get("download_token", ""))

    # Find user_id from registered connections
    connections = _load_zoom_connections()
    user_id = ""
    connection_id = ""
    for uid, cid in connections.items():
        user_id = uid
        connection_id = cid
        break

    if not user_id:
        user_id = config.DEFAULT_USER_ID

    for rf in recording_files:
        if not isinstance(rf, dict):
            continue

        file_type = rf.get("file_type", "")
        recording_type = rf.get("recording_type", "")
        download_url = rf.get("download_url", "")
        file_size = int(rf.get("file_size", 0) or 0)

        if not download_url:
            continue

        # Prioritize transcripts and audio over video (smaller, more useful for AI)
        if file_type == "TRANSCRIPT":
            await _download_and_ingest_recording(
                download_url, download_token, f"{topic} - Transcript.vtt",
                "text/vtt", user_id, topic, start_time, participants,
            )
        elif file_type == "CHAT":
            await _download_and_ingest_recording(
                download_url, download_token, f"{topic} - Chat.txt",
                "text/plain", user_id, topic, start_time, participants,
            )
        elif file_type in ("MP4", "M4A") and file_size < _MAX_FILE_SIZE:
            mime = "audio/mp4" if file_type == "M4A" else "video/mp4"
            await _download_and_ingest_recording(
                download_url, download_token, f"{topic} - {recording_type}.{file_type.lower()}",
                mime, user_id, topic, start_time, participants,
            )

    # Always ingest meeting metadata
    await _ingest_meeting_metadata(topic, host_email, start_time, duration, participants, user_id or config.DEFAULT_USER_ID)


async def _download_and_ingest_recording(
    download_url: str,
    download_token: str,
    filename: str,
    mime_type: str,
    user_id: str,
    topic: str,
    start_time: str,
    participants: list[str],
):
    """Download a Zoom recording file using the download_token and ingest it."""
    try:
        # Zoom provides a download_token for direct access
        url = f"{download_url}?access_token={download_token}" if download_token else download_url
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code != 200:
                logger.warning("Failed to download Zoom recording %s: %s", filename, resp.status_code)
                return

        content = resp.content
        if len(content) > _MAX_FILE_SIZE:
            logger.warning("Zoom recording %s too large (%d bytes), skipping", filename, len(content))
            return

        logger.info("Downloaded Zoom recording %s (%d bytes)", filename, len(content))

        is_text = mime_type.startswith("text/")

        envelope = UniversalEnvelope(
            envelope_id=uuid.uuid4().hex,
            origin=OriginDescriptor(
                source_type=SourceType.CONFERENCING,
                channel_type="zoom",
                user_id=user_id,
            ),
            payload=PayloadDescriptor(
                mime_type=mime_type,
                size_bytes=len(content),
                is_downloaded=True,
            ),
            context=ContextDescriptor(
                tags=["zoom", "recording", "meeting"],
            ),
            content_text=content.decode("utf-8", errors="replace") if is_text else None,
            content_b64=base64.b64encode(content).decode("ascii") if not is_text else None,
            content_json={
                "filename": filename,
                "topic": topic,
                "start_time": start_time,
                "participants": participants,
            },
        )

        try:
            result = await _forward_to_webhook(envelope, auth_user_id=user_id)
            logger.info("Ingested Zoom recording %s as %s (via pipeline)", filename, result.data_id)
        except Exception:
            result = await _store_direct(envelope, auth_user_id=user_id)
            logger.info("Ingested Zoom recording %s as %s (direct)", filename, result.data_id)

    except Exception:
        logger.exception("Failed to ingest Zoom recording %s", filename)


async def _ingest_meeting_metadata(
    topic: str, host_email: str, start_time: str, duration: int,
    participants: list[str], user_id: str,
):
    """Ingest meeting metadata as a text summary."""
    content = f"Zoom Meeting: {topic}\nHost: {host_email}\nStart: {start_time}\nDuration: {duration} min\nParticipants: {', '.join(participants)}"

    envelope = UniversalEnvelope(
        envelope_id=uuid.uuid4().hex,
        origin=OriginDescriptor(
            source_type=SourceType.CONFERENCING,
            channel_type="zoom",
            user_id=user_id,
        ),
        payload=PayloadDescriptor(
            mime_type="text/plain",
            is_downloaded=True,
        ),
        context=ContextDescriptor(
            tags=["zoom", "meeting", "metadata"],
        ),
        content_text=content,
        content_json={
            "topic": topic,
            "host_email": host_email,
            "start_time": start_time,
            "duration_minutes": duration,
            "participants": participants,
        },
    )

    try:
        result = await _forward_to_webhook(envelope, auth_user_id=user_id)
        logger.info("Ingested Zoom meeting metadata: %s as %s", topic, result.data_id)
    except Exception:
        result = await _store_direct(envelope, auth_user_id=user_id)
        logger.info("Ingested Zoom meeting metadata: %s as %s (direct)", topic, result.data_id)


# ---------------------------------------------------------------------------
# Connection registration
# ---------------------------------------------------------------------------

@router.post("/register")
async def register_zoom(body: ZoomRegisterRequest, request: Request):
    """Register a Zoom Nango connection for recording downloads."""
    user_id = body.user_id or getattr(request.state, "user_id", None) or config.DEFAULT_USER_ID
    connections = _load_zoom_connections()
    connections[user_id] = body.connection_id
    _save_zoom_connections()
    logger.info("Registered Zoom connection for user %s: %s", user_id, body.connection_id)
    return {"status": "registered", "user_id": user_id, "connection_id": body.connection_id}
