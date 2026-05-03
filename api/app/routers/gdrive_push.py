"""Google Drive Push Notifications via Changes API.

Receives webhook notifications when files are created/modified in the user's
Google Drive, fetches the file content via Nango proxy, and ingests into memdog.
"""

import base64
import json
import logging
import os
import uuid
from typing import Any, Optional

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

logger = logging.getLogger("mem_dog.routers.gdrive_push")

router = APIRouter(prefix="/api/v1/gdrive", tags=["Google Drive"])

_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

# Google native file types → export MIME + extension
GOOGLE_EXPORT_MAP = {
    "application/vnd.google-apps.document": ("text/plain", ".txt"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}

# Skip these MIME types
SKIP_MIME_TYPES = {
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.shortcut",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.map",
    "application/vnd.google-apps.site",
}

# ---------------------------------------------------------------------------
# Watch state persistence (file on PVC)
# ---------------------------------------------------------------------------

_WATCH_FILE = "/data/gdrive_watches.json"
_watch_cache: dict[str, dict[str, Any]] = {}
_cache_loaded = False


def _load_watches() -> dict[str, dict[str, Any]]:
    global _watch_cache, _cache_loaded
    if _cache_loaded:
        return _watch_cache
    try:
        if os.path.exists(_WATCH_FILE):
            with open(_WATCH_FILE) as f:
                _watch_cache = json.load(f)
            logger.info("Loaded %d gdrive watches from %s", len(_watch_cache), _WATCH_FILE)
    except Exception:
        logger.debug("No persisted gdrive watches found, starting fresh")
    _cache_loaded = True
    return _watch_cache


def _save_watches():
    try:
        os.makedirs(os.path.dirname(_WATCH_FILE), exist_ok=True)
        with open(_WATCH_FILE, "w") as f:
            json.dump(_watch_cache, f)
    except Exception:
        logger.warning("Failed to persist gdrive watches")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class WatchRequest(BaseModel):
    connection_id: str
    user_id: str = ""


class WatchResponse(BaseModel):
    channel_id: str
    expiration: str
    page_token: str
    status: str = "active"


# ---------------------------------------------------------------------------
# Webhook receiver (called by Google, no auth)
# ---------------------------------------------------------------------------

@router.post("/push")
async def gdrive_push(request: Request, background_tasks: BackgroundTasks):
    """Receive Google Drive change notification.

    Google sends headers:
    - X-Goog-Channel-ID: our channel UUID
    - X-Goog-Resource-State: sync | change | ...
    - X-Goog-Resource-ID: Google's resource ID
    """
    channel_id = request.headers.get("x-goog-channel-id", "")
    resource_state = request.headers.get("x-goog-resource-state", "")

    if resource_state == "sync":
        logger.info("Drive watch sync handshake for channel %s", channel_id)
        return {"status": "sync ok"}

    if resource_state != "change":
        return {"status": "ignored", "state": resource_state}

    logger.info("Drive change notification for channel %s", channel_id)

    # Find watch by channel_id
    watches = _load_watches()
    watch = None
    for uid, state in watches.items():
        if state.get("channel_id") == channel_id:
            watch = state
            watch["user_id"] = uid
            break

    if not watch:
        logger.warning("No watch registered for channel %s, ignoring", channel_id)
        return {"status": "no watch"}

    background_tasks.add_task(_process_drive_changes, watch=watch)
    return {"status": "ok"}


async def _process_drive_changes(watch: dict):
    """Fetch changed files and ingest them."""
    connection_id = watch["connection_id"]
    page_token = watch.get("page_token", "")
    user_id = watch.get("user_id", config.DEFAULT_USER_ID)

    if not page_token:
        logger.warning("No page_token for drive watch, skipping")
        return

    try:
        resp = await proxy_request(
            connection_id=connection_id,
            provider_config_key="google-drive",
            method="GET",
            path="drive/v3/changes",
            params={
                "pageToken": page_token,
                "fields": "newStartPageToken,nextPageToken,changes(fileId,removed,file(id,name,mimeType,size,modifiedTime,trashed))",
                "includeRemoved": "false",
                "spaces": "drive",
            },
        )

        if resp.status_code != 200:
            logger.error("Drive changes.list failed: %s %s", resp.status_code, resp.text[:200])
            return

        data = resp.json()
        changes = data.get("changes", [])

        logger.info("Found %d drive changes for user %s", len(changes), user_id)

        for change in changes:
            if change.get("removed"):
                continue
            file_info = change.get("file", {})
            if not file_info:
                continue
            if file_info.get("trashed"):
                continue
            mime_type = file_info.get("mimeType", "")
            if mime_type in SKIP_MIME_TYPES:
                continue

            file_id = file_info.get("id", "")
            file_name = file_info.get("name", "")
            file_size = int(file_info.get("size", 0) or 0)

            if file_size > _MAX_FILE_SIZE and mime_type not in GOOGLE_EXPORT_MAP:
                logger.warning("Skipping large file %s (%d bytes)", file_name, file_size)
                continue

            await _fetch_and_ingest_file(connection_id, file_id, file_name, mime_type, user_id)

        # Update page token
        new_token = data.get("newStartPageToken", data.get("nextPageToken", page_token))
        watch["page_token"] = new_token
        _save_watches()

    except Exception:
        logger.exception("Failed to process Drive changes for user %s", user_id)


async def _fetch_and_ingest_file(
    connection_id: str, file_id: str, file_name: str, mime_type: str, user_id: str,
):
    """Fetch a file from Google Drive and ingest it."""
    try:
        # Google native files need export
        if mime_type in GOOGLE_EXPORT_MAP:
            export_mime, ext = GOOGLE_EXPORT_MAP[mime_type]
            resp = await proxy_request(
                connection_id=connection_id,
                provider_config_key="google-drive",
                method="GET",
                path=f"drive/v3/files/{file_id}/export",
                params={"mimeType": export_mime},
            )
            effective_mime = export_mime
        else:
            resp = await proxy_request(
                connection_id=connection_id,
                provider_config_key="google-drive",
                method="GET",
                path=f"drive/v3/files/{file_id}",
                params={"alt": "media"},
            )
            effective_mime = mime_type

        if resp.status_code != 200:
            logger.warning("Failed to fetch file %s: %s", file_name, resp.status_code)
            return

        content = resp.content
        if len(content) > _MAX_FILE_SIZE:
            logger.warning("File %s too large after download (%d bytes), skipping", file_name, len(content))
            return

        logger.info("Downloaded Drive file %s (%d bytes, %s)", file_name, len(content), effective_mime)

        # Build envelope
        is_text = effective_mime.startswith("text/") or effective_mime == "application/json"

        if is_text:
            content_text = content.decode("utf-8", errors="replace")
            content_b64 = None
        else:
            content_text = None
            content_b64 = base64.b64encode(content).decode("ascii")

        # Text content → OTHER source type (avoids binary PDF agent routing)
        # Binary content → DOCUMENT source type
        source_type = SourceType.OTHER if is_text else SourceType.DOCUMENT

        envelope = UniversalEnvelope(
            envelope_id=uuid.uuid4().hex,
            origin=OriginDescriptor(
                source_type=source_type,
                channel_type="google_docs",
                user_id=user_id,
            ),
            payload=PayloadDescriptor(
                mime_type=effective_mime,
                size_bytes=len(content),
                is_downloaded=True,
            ),
            context=ContextDescriptor(
                tags=["google-drive", "drive", "auto-sync"],
            ),
            content_text=content_text,
            content_b64=content_b64,
            content_json={
                "filename": file_name,
                "mime_type": effective_mime,
                "original_mime_type": mime_type,
                "drive_file_id": file_id,
            },
        )

        try:
            result = await _forward_to_webhook(envelope, auth_user_id=user_id)
            logger.info("Ingested Drive file %s as %s (via pipeline)", file_name, result.data_id)
        except Exception:
            logger.warning("Pipeline unavailable, storing Drive file %s directly", file_name)
            result = await _store_direct(envelope, auth_user_id=user_id)
            logger.info("Ingested Drive file %s as %s (direct)", file_name, result.data_id)

    except Exception:
        logger.exception("Failed to ingest Drive file %s", file_name)


# ---------------------------------------------------------------------------
# Watch management
# ---------------------------------------------------------------------------

@router.post("/watch", response_model=WatchResponse)
async def start_watch(body: WatchRequest, request: Request):
    """Register Google Drive change notifications for a connected account."""
    user_id = body.user_id or getattr(request.state, "user_id", None) or config.DEFAULT_USER_ID
    webhook_url = os.getenv("NANGO_SERVER_URL", "").rstrip("/")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="NANGO_SERVER_URL not set — needed for webhook callback URL")

    try:
        # Get initial page token
        token_resp = await proxy_request(
            connection_id=body.connection_id,
            provider_config_key="google-drive",
            method="GET",
            path="drive/v3/changes/startPageToken",
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=token_resp.status_code, detail=token_resp.text)
        page_token = token_resp.json().get("startPageToken", "")

        # Register watch channel
        channel_id = str(uuid.uuid4())
        watch_resp = await proxy_request(
            connection_id=body.connection_id,
            provider_config_key="google-drive",
            method="POST",
            path=f"drive/v3/changes/watch?pageToken={page_token}",
            body=json.dumps({
                "id": channel_id,
                "type": "web_hook",
                "address": f"{webhook_url}/gke-api/api/v1/gdrive/push",
            }).encode(),
        )

        if watch_resp.status_code != 200:
            raise HTTPException(status_code=watch_resp.status_code, detail=watch_resp.text)

        watch_data = watch_resp.json()
        resource_id = watch_data.get("resourceId", "")
        expiration = str(watch_data.get("expiration", ""))

        # Store watch state
        watches = _load_watches()
        watches[user_id] = {
            "connection_id": body.connection_id,
            "channel_id": channel_id,
            "resource_id": resource_id,
            "page_token": page_token,
            "expiration": expiration,
            "status": "active",
        }
        _save_watches()

        logger.info("Drive watch started for user %s, channel=%s, pageToken=%s", user_id, channel_id, page_token)

        return WatchResponse(
            channel_id=channel_id,
            expiration=expiration,
            page_token=page_token,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("start_watch failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/watch")
async def stop_watch(request: Request):
    """Stop Google Drive change notifications."""
    user_id = getattr(request.state, "user_id", None) or config.DEFAULT_USER_ID
    watches = _load_watches()
    watch = watches.get(user_id)
    if not watch:
        return {"status": "no active watch"}

    try:
        await proxy_request(
            connection_id=watch["connection_id"],
            provider_config_key="google-drive",
            method="POST",
            path="drive/v3/channels/stop",
            body=json.dumps({
                "id": watch["channel_id"],
                "resourceId": watch["resource_id"],
            }).encode(),
        )
    except Exception:
        pass

    watch["status"] = "stopped"
    _save_watches()
    return {"status": "stopped"}


@router.post("/watch/renew")
async def renew_watches():
    """Renew all active Drive watches (call every 12 hours)."""
    renewed = 0
    watches = _load_watches()
    webhook_url = os.getenv("NANGO_SERVER_URL", "").rstrip("/")

    for user_id, watch in watches.items():
        if watch.get("status") != "active":
            continue
        try:
            # Stop old channel
            await proxy_request(
                connection_id=watch["connection_id"],
                provider_config_key="google-drive",
                method="POST",
                path="drive/v3/channels/stop",
                body=json.dumps({
                    "id": watch["channel_id"],
                    "resourceId": watch.get("resource_id", ""),
                }).encode(),
            )

            # Register new channel
            channel_id = str(uuid.uuid4())
            page_token = watch.get("page_token", "1")
            resp = await proxy_request(
                connection_id=watch["connection_id"],
                provider_config_key="google-drive",
                method="POST",
                path=f"drive/v3/changes/watch?pageToken={page_token}",
                body=json.dumps({
                    "id": channel_id,
                    "type": "web_hook",
                    "address": f"{webhook_url}/gke-api/api/v1/gdrive/push",
                }).encode(),
            )
            if resp.status_code == 200:
                data = resp.json()
                watch["channel_id"] = channel_id
                watch["resource_id"] = data.get("resourceId", "")
                watch["expiration"] = str(data.get("expiration", ""))
                renewed += 1
        except Exception:
            logger.exception("Failed to renew Drive watch for user %s", user_id)

    _save_watches()
    return {"renewed": renewed, "total": len(watches)}
