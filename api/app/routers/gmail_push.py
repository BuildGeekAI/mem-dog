"""Gmail Push Notifications via Google Pub/Sub.

Receives Pub/Sub push messages when new emails arrive, fetches the email
content via Nango proxy (auto token refresh), and ingests into mem-dog.
"""

import base64
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app import config
from app.nango_client import proxy_request, NANGO_SECRET_KEY
from app.models import (
    UniversalEnvelope,
    OriginDescriptor,
    PayloadDescriptor,
    ContextDescriptor,
    SourceType,
)
from app.routers.ingest import _forward_to_webhook, _store_direct

from app.storage import get_storage

logger = logging.getLogger("mem_dog.routers.gmail_push")

router = APIRouter(prefix="/api/v1/gmail", tags=["Gmail"])

GMAIL_TOPIC = f"projects/{config.GCP_PROJECT_ID or 'memdog-dev'}/topics/gmail-push-notifications"

# Watch state — persisted via storage so it survives pod restarts
_WATCH_BLOB_KEY = "system/gmail_watches.json"
_watch_cache: dict[str, dict[str, Any]] = {}  # in-memory cache, loaded from storage on first use
_cache_loaded = False


_WATCH_FILE = "/data/gmail_watches.json"


def _load_watches() -> dict[str, dict[str, Any]]:
    """Load watch state from persistent file on the PVC."""
    global _watch_cache, _cache_loaded
    if _cache_loaded:
        return _watch_cache
    try:
        import os
        if os.path.exists(_WATCH_FILE):
            with open(_WATCH_FILE) as f:
                _watch_cache = json.load(f)
            logger.info("Loaded %d gmail watches from %s", len(_watch_cache), _WATCH_FILE)
    except Exception:
        logger.debug("No persisted gmail watches found, starting fresh")
    _cache_loaded = True
    return _watch_cache


def _save_watches():
    """Persist watch state to file on the PVC."""
    try:
        import os
        os.makedirs(os.path.dirname(_WATCH_FILE), exist_ok=True)
        with open(_WATCH_FILE, "w") as f:
            json.dump(_watch_cache, f)
    except Exception:
        logger.warning("Failed to persist gmail watches")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class WatchRequest(BaseModel):
    connection_id: str
    user_id: str = ""
    label_ids: list[str] = ["INBOX"]


class WatchResponse(BaseModel):
    email_address: str
    history_id: str
    expiration: str
    status: str = "active"


# ---------------------------------------------------------------------------
# Pub/Sub push handler (called by GCP, no auth)
# ---------------------------------------------------------------------------

@router.post("/push")
async def gmail_push(request: Request, background_tasks: BackgroundTasks):
    """Receive Gmail push notification from Pub/Sub.

    Pub/Sub sends: {"message": {"data": "<base64>", "messageId": "..."}}
    Decoded data: {"emailAddress": "user@gmail.com", "historyId": 12345}
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid body"}

    message = body.get("message", {})
    data_b64 = message.get("data", "")
    if not data_b64:
        return {"status": "no data"}

    try:
        data = json.loads(base64.b64decode(data_b64))
    except Exception:
        return {"status": "invalid data"}

    email_address = data.get("emailAddress", "")
    new_history_id = str(data.get("historyId", ""))

    if not email_address:
        return {"status": "no email"}

    logger.info("Gmail push notification for %s, historyId=%s", email_address, new_history_id)

    # Find the watch state for this email
    watches = _load_watches()
    watch = None
    for uid, state in watches.items():
        if state.get("email_address") == email_address:
            watch = state
            watch["user_id"] = uid
            break

    if not watch:
        logger.warning("No watch registered for %s, ignoring", email_address)
        return {"status": "no watch"}

    # Process in background so we ACK Pub/Sub quickly
    background_tasks.add_task(
        _process_gmail_notification,
        watch=watch,
        new_history_id=new_history_id,
    )

    return {"status": "ok"}


async def _process_gmail_notification(watch: dict, new_history_id: str):
    """Fetch new emails since last history_id and ingest them."""
    connection_id = watch["connection_id"]
    old_history_id = watch.get("history_id", "")
    user_id = watch.get("user_id", config.DEFAULT_USER_ID)

    if not old_history_id:
        old_history_id = new_history_id
        watch["history_id"] = new_history_id
        return

    try:
        # Get history of changes since last known point
        resp = await proxy_request(
            connection_id=connection_id,
            provider_config_key="google-mail",
            method="GET",
            path="gmail/v1/users/me/history",
            params={
                "startHistoryId": old_history_id,
                "historyTypes": "messageAdded",
                "labelIds": "INBOX",
            },
        )

        if resp.status_code == 404:
            # historyId expired, skip this notification
            logger.warning("Gmail historyId expired for %s, updating to %s", watch["email_address"], new_history_id)
            watch["history_id"] = new_history_id
            return

        if resp.status_code != 200:
            logger.error("Gmail history.list failed: %s %s", resp.status_code, resp.text[:200])
            return

        history_data = resp.json()
        history_list = history_data.get("history", [])

        # Collect unique new message IDs
        new_message_ids: set[str] = set()
        for entry in history_list:
            for msg_added in entry.get("messagesAdded", []):
                msg = msg_added.get("message", {})
                msg_id = msg.get("id")
                if msg_id:
                    new_message_ids.add(msg_id)

        logger.info("Found %d new messages for %s", len(new_message_ids), watch["email_address"])

        # Fetch and ingest each new message
        for msg_id in list(new_message_ids)[:20]:  # cap at 20 per notification
            await _fetch_and_ingest_email(connection_id, msg_id, user_id)

        # Update history_id and persist
        watch["history_id"] = history_data.get("historyId", new_history_id)
        _save_watches()

    except Exception:
        logger.exception("Failed to process Gmail notification for %s", watch["email_address"])


async def _fetch_and_ingest_email(connection_id: str, message_id: str, user_id: str):
    """Fetch a single email via Nango proxy and ingest it."""
    try:
        resp = await proxy_request(
            connection_id=connection_id,
            provider_config_key="google-mail",
            method="GET",
            path=f"gmail/v1/users/me/messages/{message_id}",
            params={"format": "full"},
        )

        if resp.status_code != 200:
            logger.warning("Failed to fetch message %s: %s", message_id, resp.status_code)
            return

        msg = resp.json()
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

        subject = headers.get("subject", "(no subject)")
        sender = headers.get("from", "unknown")
        date = headers.get("date", "")
        snippet = msg.get("snippet", "")

        # Extract body text
        body_text = _extract_body(msg.get("payload", {}))

        # Build content for ingestion
        content = f"From: {sender}\nSubject: {subject}\nDate: {date}\n\n{body_text or snippet}"

        # Build UniversalEnvelope and forward through the webhook pipeline
        envelope = UniversalEnvelope(
            envelope_id=uuid.uuid4().hex,
            origin=OriginDescriptor(
                source_type=SourceType.EMAIL,
                channel_type="email",
                user_id=user_id,
            ),
            payload=PayloadDescriptor(
                mime_type="text/plain",
                is_downloaded=True,
            ),
            context=ContextDescriptor(
                tags=["gmail", "email", "push-notification"],
            ),
            content_text=content,
            content_json={
                "subject": subject,
                "from": sender,
                "date": date,
                "body": body_text or snippet,
                "gmail_message_id": message_id,
                "headers": headers,
            },
        )

        try:
            result = await _forward_to_webhook(envelope, auth_user_id=user_id)
            logger.info("Ingested Gmail message %s as %s (via pipeline): %s", message_id, result.data_id, subject)
        except Exception:
            # Pipeline unavailable — fall back to direct storage
            logger.warning("Pipeline unavailable, storing Gmail message %s directly", message_id)
            result = await _store_direct(envelope, auth_user_id=user_id)
            logger.info("Ingested Gmail message %s as %s (direct): %s", message_id, result.data_id, subject)

        # Ingest attachments
        attachments = _find_attachments(msg.get("payload", {}))
        for att in attachments:
            await _fetch_and_ingest_attachment(
                connection_id, message_id, att, user_id, subject,
            )

    except Exception:
        logger.exception("Failed to ingest Gmail message %s", message_id)


def _extract_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    # Direct body
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    if mime == "text/plain" and body.get("data"):
        return base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="replace")

    # Multipart — look for text/plain part
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Fallback — try text/html
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                # Strip HTML tags (basic)
                import re
                return re.sub(r"<[^>]+>", " ", html).strip()

    # Nested multipart
    for part in payload.get("parts", []):
        if part.get("parts"):
            result = _extract_body(part)
            if result:
                return result

    return ""


# ---------------------------------------------------------------------------
# Attachment handling
# ---------------------------------------------------------------------------

def _find_attachments(payload: dict) -> list[dict]:
    """Recursively find all parts with attachments (filename + attachmentId)."""
    attachments = []
    body = payload.get("body", {})
    filename = payload.get("filename", "")
    attachment_id = body.get("attachmentId", "")

    if filename and attachment_id:
        attachments.append({
            "filename": filename,
            "attachment_id": attachment_id,
            "mime_type": payload.get("mimeType", "application/octet-stream"),
            "size": body.get("size", 0),
        })

    for part in payload.get("parts", []):
        attachments.extend(_find_attachments(part))

    return attachments


async def _fetch_and_ingest_attachment(
    connection_id: str,
    message_id: str,
    attachment: dict,
    user_id: str,
    email_subject: str,
):
    """Fetch a Gmail attachment and ingest it through the pipeline."""
    filename = attachment["filename"]
    attachment_id = attachment["attachment_id"]
    mime_type = attachment["mime_type"]

    try:
        resp = await proxy_request(
            connection_id=connection_id,
            provider_config_key="google-mail",
            method="GET",
            path=f"gmail/v1/users/me/messages/{message_id}/attachments/{attachment_id}",
        )

        if resp.status_code != 200:
            logger.warning("Failed to fetch attachment %s from message %s: %s", filename, message_id, resp.status_code)
            return

        att_data = resp.json()
        raw_b64 = att_data.get("data", "")
        if not raw_b64:
            return

        # Gmail uses URL-safe base64 — convert to standard base64 for the envelope
        raw_b64_std = raw_b64.replace("-", "+").replace("_", "/")
        # Add padding if needed
        padding = 4 - len(raw_b64_std) % 4
        if padding != 4:
            raw_b64_std += "=" * padding

        envelope = UniversalEnvelope(
            envelope_id=uuid.uuid4().hex,
            origin=OriginDescriptor(
                source_type=SourceType.DOCUMENT if _is_document(mime_type) else SourceType.BINARY,
                channel_type="email",
                user_id=user_id,
            ),
            payload=PayloadDescriptor(
                mime_type=mime_type,
                size_bytes=attachment.get("size", 0),
                is_downloaded=True,
            ),
            context=ContextDescriptor(
                tags=["gmail", "email", "attachment"],
            ),
            content_b64=raw_b64_std,
            content_json={
                "filename": filename,
                "mime_type": mime_type,
                "gmail_message_id": message_id,
                "email_subject": email_subject,
            },
        )

        try:
            result = await _forward_to_webhook(envelope, auth_user_id=user_id)
            logger.info("Ingested attachment %s as %s (via pipeline)", filename, result.data_id)
        except Exception:
            logger.warning("Pipeline unavailable, storing attachment %s directly", filename)
            result = await _store_direct(envelope, auth_user_id=user_id)
            logger.info("Ingested attachment %s as %s (direct)", filename, result.data_id)

    except Exception:
        logger.exception("Failed to ingest attachment %s from message %s", filename, message_id)


def _is_document(mime_type: str) -> bool:
    """Check if MIME type is a document (PDF, Office, text)."""
    doc_types = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "text/csv",
        "text/plain",
    }
    return mime_type in doc_types or mime_type.startswith("text/")


# ---------------------------------------------------------------------------
# Watch management
# ---------------------------------------------------------------------------

@router.post("/watch", response_model=WatchResponse)
async def start_watch(body: WatchRequest, request: Request):
    """Register Gmail push notifications for a connected account."""
    user_id = body.user_id or getattr(request.state, "user_id", None) or config.DEFAULT_USER_ID

    try:
        # Call Gmail users.watch() via Nango proxy
        resp = await proxy_request(
            connection_id=body.connection_id,
            provider_config_key="google-mail",
            method="POST",
            path="gmail/v1/users/me/watch",
            body=json.dumps({
                "topicName": GMAIL_TOPIC,
                "labelIds": body.label_ids,
            }).encode(),
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        watch_data = resp.json()
        history_id = str(watch_data.get("historyId", ""))
        expiration = str(watch_data.get("expiration", ""))

        # Get user's email address
        profile_resp = await proxy_request(
            connection_id=body.connection_id,
            provider_config_key="google-mail",
            method="GET",
            path="gmail/v1/users/me/profile",
        )
        email_address = ""
        if profile_resp.status_code == 200:
            email_address = profile_resp.json().get("emailAddress", "")

        # Store watch state (persisted)
        watches = _load_watches()
        watches[user_id] = {
            "connection_id": body.connection_id,
            "email_address": email_address,
            "history_id": history_id,
            "expiration": expiration,
            "status": "active",
        }

        _save_watches()
        logger.info("Gmail watch started for %s (user %s), historyId=%s", email_address, user_id, history_id)

        return WatchResponse(
            email_address=email_address,
            history_id=history_id,
            expiration=expiration,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("start_watch failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/watch")
async def stop_watch(request: Request):
    """Stop Gmail push notifications."""
    user_id = getattr(request.state, "user_id", None) or config.DEFAULT_USER_ID
    watches = _load_watches()
    watch = watches.get(user_id)
    if not watch:
        return {"status": "no active watch"}

    try:
        await proxy_request(
            connection_id=watch["connection_id"],
            provider_config_key="google-mail",
            method="POST",
            path="gmail/v1/users/me/stop",
        )
    except Exception:
        pass

    watch["status"] = "stopped"
    _save_watches()
    return {"status": "stopped"}


@router.post("/watch/renew")
async def renew_watches():
    """Renew all active Gmail watches (call daily or via Cloud Scheduler)."""
    renewed = 0
    watches = _load_watches()
    for user_id, watch in watches.items():
        if watch.get("status") != "active":
            continue
        try:
            resp = await proxy_request(
                connection_id=watch["connection_id"],
                provider_config_key="google-mail",
                method="POST",
                path="gmail/v1/users/me/watch",
                body=json.dumps({
                    "topicName": GMAIL_TOPIC,
                    "labelIds": ["INBOX"],
                }).encode(),
            )
            if resp.status_code == 200:
                data = resp.json()
                watch["history_id"] = str(data.get("historyId", watch["history_id"]))
                watch["expiration"] = str(data.get("expiration", ""))
                renewed += 1
        except Exception:
            logger.exception("Failed to renew watch for user %s", user_id)

    _save_watches()
    return {"renewed": renewed, "total": len(watches)}
