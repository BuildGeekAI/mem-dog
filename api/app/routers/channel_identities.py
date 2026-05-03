"""Channel identity correlation API.

CRUD and lookup for channel_type + channel_unique_id <-> user_id bindings.
See docs/plan/channel_identity_correlation.md and docs/api/channel-identities-api.md.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import (
    ChannelIdentityCreate,
    ChannelIdentityUpdate,
    ChannelIdentityRecord,
    ChannelIdentityListResponse,
)
from app.storage import get_storage

logger = logging.getLogger("mem_dog.routers.channel_identities")

router = APIRouter(prefix="/api/v1/channel-identities", tags=["Channel Identities"])


@router.post("", response_model=ChannelIdentityRecord, status_code=201)
async def create_channel_identity(body: ChannelIdentityCreate) -> ChannelIdentityRecord:
    """Create or upsert a channel identity binding. Idempotent: existing binding is updated."""
    storage = get_storage()
    try:
        return storage.channel_identity_create(body)
    except Exception as exc:
        logger.exception("channel_identity_create failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/by-channel", response_model=ChannelIdentityRecord)
async def get_by_channel(
    channel_type: str = Query(..., description="Channel type (e.g. telegram, slack)"),
    channel_unique_id: str = Query(..., description="Unique id of the identity on that channel"),
) -> ChannelIdentityRecord:
    """Return the user_id and metadata for this channel identity, or 404."""
    storage = get_storage()
    record = storage.channel_identity_get_by_channel(channel_type, channel_unique_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No identity for channel_type={channel_type!r} channel_unique_id={channel_unique_id!r}",
        )
    return record


@router.get("/by-user/{user_id}", response_model=ChannelIdentityListResponse)
async def list_by_user(user_id: str) -> ChannelIdentityListResponse:
    """List all channel identities linked to this user."""
    storage = get_storage()
    return storage.channel_identity_list_by_user(user_id)


@router.patch("/by-channel", response_model=ChannelIdentityRecord)
async def update_channel_identity(
    body: ChannelIdentityUpdate,
    channel_type: str = Query(..., description="Channel type"),
    channel_unique_id: str = Query(..., description="Channel unique id"),
) -> ChannelIdentityRecord:
    """Update display_name and/or metadata for an existing binding. Returns 404 if not found."""
    storage = get_storage()
    record = storage.channel_identity_update(
        channel_type,
        channel_unique_id,
        display_name=body.display_name,
        metadata=body.metadata,
    )
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No identity for channel_type={channel_type!r} channel_unique_id={channel_unique_id!r}",
        )
    return record


@router.delete("/by-channel", status_code=204)
async def delete_channel_identity(
    channel_type: str = Query(..., description="Channel type"),
    channel_unique_id: str = Query(..., description="Channel unique id"),
) -> None:
    """Remove the channel identity binding. 204 if deleted, 404 if not found."""
    storage = get_storage()
    deleted = storage.channel_identity_delete(channel_type, channel_unique_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No identity for channel_type={channel_type!r} channel_unique_id={channel_unique_id!r}",
        )
