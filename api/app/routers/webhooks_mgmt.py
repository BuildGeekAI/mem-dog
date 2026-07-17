"""Per-user webhook endpoint management — create, list, update, delete webhook URLs.

Each webhook has a unique ``whk_<ulid>`` ID. External services POST to
``/webhooks/{webhook_id}`` on the gateway. The gateway resolves the webhook
record to get user_id and channel_type, eliminating identity heuristics.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app import config
from app.ids import generate_webhook_id, generate_event_id
from app.models import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookEventResponse,
    WebhookStatus,
)
from app.storage import get_storage

logger = logging.getLogger("mem_dog.routers.webhooks_mgmt")

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])

_WEBHOOKS_TABLE = "webhooks"
_EVENTS_TABLE = "webhook_events"


def _get_supabase_client():
    """Get the shared Supabase client from storage."""
    storage = get_storage()
    if not hasattr(storage, "_supa_client"):
        raise HTTPException(
            status_code=503,
            detail="Supabase storage not configured. Webhooks require Supabase.",
        )
    return storage._supa_client


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_user_id(request: Request) -> str:
    """Extract authenticated user_id from request state."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


def _build_url(webhook_id: str) -> Optional[str]:
    """Construct the inbound webhook URL if gateway URL is configured."""
    gw = config.WEBHOOK_GATEWAY_URL
    if not gw:
        return None
    base = gw.rstrip("/")
    return f"{base}/webhooks/{webhook_id}"


def _row_to_response(row: Dict[str, Any], *, secret: str | None = None) -> WebhookResponse:
    """Convert a DB row to a WebhookResponse."""
    return WebhookResponse(
        webhook_id=row["webhook_id"],
        user_id=row["user_id"],
        channel_type=row["channel_type"],
        name=row.get("name", ""),
        status=row.get("status", "active"),
        url=_build_url(row["webhook_id"]),
        secret=secret,
        config=row.get("config") or {},
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


# -------------------------------------------------------------------------
# CRUD
# -------------------------------------------------------------------------


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(body: WebhookCreate, request: Request):
    """Create a new webhook endpoint for the authenticated user."""
    user_id = _get_user_id(request)
    client = _get_supabase_client()

    webhook_id = generate_webhook_id()
    now = _now_iso()

    raw_secret: str | None = None
    secret_hash: str | None = None
    if body.generate_secret:
        raw_secret = f"whk_sec_{secrets.token_urlsafe(32)}"
        secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

    row = {
        "webhook_id": webhook_id,
        "user_id": user_id,
        "channel_type": body.channel_type,
        "name": body.name,
        "secret_hash": secret_hash,
        "status": WebhookStatus.ACTIVE.value,
        "config": body.config,
        "created_at": now,
        "updated_at": now,
    }

    try:
        res = client.table(_WEBHOOKS_TABLE).insert(row).execute()
    except Exception as exc:
        logger.error("Failed to create webhook: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create webhook")

    created = res.data[0] if res.data else row
    return _row_to_response(created, secret=raw_secret)


@router.get("", response_model=List[WebhookResponse])
async def list_webhooks(
    request: Request,
    channel_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List webhooks for the authenticated user."""
    user_id = _get_user_id(request)
    client = _get_supabase_client()

    query = client.table(_WEBHOOKS_TABLE).select("*").eq("user_id", user_id)
    if channel_type:
        query = query.eq("channel_type", channel_type)
    if status:
        query = query.eq("status", status)
    else:
        query = query.neq("status", "deleted")

    query = query.order("created_at", desc=True)

    try:
        res = query.execute()
    except Exception as exc:
        logger.error("Failed to list webhooks: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to list webhooks")

    return [_row_to_response(r) for r in (res.data or [])]


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(webhook_id: str, request: Request):
    """Get a single webhook by ID.

    Workspace keys must own the webhook. Platform ``API_KEY`` (auth_type=global)
    may look up any webhook for gateway service resolution (secret never returned).
    """
    auth_type = getattr(request.state, "auth_type", None)
    client = _get_supabase_client()

    try:
        res = (
            client.table(_WEBHOOKS_TABLE)
            .select("*")
            .eq("webhook_id", webhook_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to get webhook %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to get webhook")

    if not res.data:
        raise HTTPException(status_code=404, detail="Webhook not found")

    row = res.data[0]
    if auth_type != "global":
        user_id = _get_user_id(request)
        if row["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Webhook not found")

    return _row_to_response(row)


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(webhook_id: str, body: WebhookUpdate, request: Request):
    """Update a webhook's name, status, channel_type, or config."""
    user_id = _get_user_id(request)
    client = _get_supabase_client()

    # Verify ownership
    try:
        res = (
            client.table(_WEBHOOKS_TABLE)
            .select("*")
            .eq("webhook_id", webhook_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch webhook %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update webhook")

    if not res.data or res.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Webhook not found")

    updates: Dict[str, Any] = {"updated_at": _now_iso()}
    if body.name is not None:
        updates["name"] = body.name
    if body.channel_type is not None:
        updates["channel_type"] = body.channel_type
    if body.status is not None:
        updates["status"] = body.status.value
    if body.config is not None:
        updates["config"] = body.config

    try:
        res = (
            client.table(_WEBHOOKS_TABLE)
            .update(updates)
            .eq("webhook_id", webhook_id)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to update webhook %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update webhook")

    updated = res.data[0] if res.data else {**res.data[0], **updates} if res.data else updates
    # Re-fetch to ensure consistency
    try:
        res = (
            client.table(_WEBHOOKS_TABLE)
            .select("*")
            .eq("webhook_id", webhook_id)
            .limit(1)
            .execute()
        )
        updated = res.data[0]
    except Exception:
        pass

    return _row_to_response(updated)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: str, request: Request):
    """Soft-delete a webhook (sets status to 'deleted', revokes the URL)."""
    user_id = _get_user_id(request)
    client = _get_supabase_client()

    # Verify ownership
    try:
        res = (
            client.table(_WEBHOOKS_TABLE)
            .select("webhook_id, user_id")
            .eq("webhook_id", webhook_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch webhook %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete webhook")

    if not res.data or res.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Webhook not found")

    try:
        client.table(_WEBHOOKS_TABLE).update(
            {"status": "deleted", "updated_at": _now_iso()}
        ).eq("webhook_id", webhook_id).execute()
    except Exception as exc:
        logger.error("Failed to delete webhook %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete webhook")

    return None


# -------------------------------------------------------------------------
# Secret rotation
# -------------------------------------------------------------------------


@router.post("/{webhook_id}/rotate-secret", response_model=WebhookResponse)
async def rotate_secret(webhook_id: str, request: Request):
    """Generate a new signing secret for an existing webhook."""
    user_id = _get_user_id(request)
    client = _get_supabase_client()

    try:
        res = (
            client.table(_WEBHOOKS_TABLE)
            .select("*")
            .eq("webhook_id", webhook_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch webhook %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to rotate secret")

    if not res.data or res.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Webhook not found")

    raw_secret = f"whk_sec_{secrets.token_urlsafe(32)}"
    secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

    try:
        client.table(_WEBHOOKS_TABLE).update(
            {"secret_hash": secret_hash, "updated_at": _now_iso()}
        ).eq("webhook_id", webhook_id).execute()
    except Exception as exc:
        logger.error("Failed to rotate secret for %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to rotate secret")

    row = res.data[0]
    row["secret_hash"] = secret_hash
    row["updated_at"] = _now_iso()
    return _row_to_response(row, secret=raw_secret)


# -------------------------------------------------------------------------
# Events / insights
# -------------------------------------------------------------------------


@router.get("/{webhook_id}/events", response_model=List[WebhookEventResponse])
async def list_webhook_events(
    webhook_id: str,
    request: Request,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List event log entries for a webhook."""
    user_id = _get_user_id(request)
    client = _get_supabase_client()

    # Verify ownership
    try:
        wh = (
            client.table(_WEBHOOKS_TABLE)
            .select("user_id")
            .eq("webhook_id", webhook_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch webhook %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to list events")

    if not wh.data or wh.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Webhook not found")

    query = (
        client.table(_EVENTS_TABLE)
        .select("*")
        .eq("webhook_id", webhook_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if status:
        query = query.eq("status", status)

    try:
        res = query.execute()
    except Exception as exc:
        logger.error("Failed to list events for %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to list events")

    return res.data or []


@router.get("/{webhook_id}/stats")
async def get_webhook_stats(
    webhook_id: str,
    request: Request,
    period: str = Query("24h", description="Stats period: 1h, 24h, 7d, 30d"),
):
    """Get aggregated stats for a webhook."""
    user_id = _get_user_id(request)
    client = _get_supabase_client()

    # Verify ownership
    try:
        wh = (
            client.table(_WEBHOOKS_TABLE)
            .select("user_id")
            .eq("webhook_id", webhook_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch webhook %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to get stats")

    if not wh.data or wh.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Parse period to a cutoff timestamp
    import re
    match = re.match(r"^(\d+)(h|d)$", period)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid period. Use e.g. 1h, 24h, 7d, 30d")

    amount, unit = int(match.group(1)), match.group(2)
    from datetime import timedelta
    delta = timedelta(hours=amount) if unit == "h" else timedelta(days=amount)
    cutoff = (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        res = (
            client.table(_EVENTS_TABLE)
            .select("status")
            .eq("webhook_id", webhook_id)
            .gte("created_at", cutoff)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to get stats for %s: %s", webhook_id, exc)
        raise HTTPException(status_code=500, detail="Failed to get stats")

    rows = res.data or []
    total = len(rows)
    by_status: Dict[str, int] = {}
    for r in rows:
        s = r.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    completed = by_status.get("completed", 0) + by_status.get("accepted", 0)
    success_rate = round(completed / total, 4) if total > 0 else 0.0

    return {
        "webhook_id": webhook_id,
        "period": period,
        "total": total,
        "by_status": by_status,
        "success_rate": success_rate,
    }
