"""Channels bucket API — per-channel metadata (path <channel>/meta).

Stores metadata and config for each channel (how to communicate, webhook URL, etc.).
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from app.models import ChannelMetadata, ChannelMetadataCreate
from app.storage import get_storage

logger = logging.getLogger("mem_dog.routers.channels")

router = APIRouter(prefix="/api/v1/channels", tags=["Channels"])


def _sanitize_channel_type(channel_type: str) -> str:
    """Normalize for path: lowercase, no slashes."""
    return (channel_type or "").strip().lower().replace("/", "_").replace("\\", "_") or "unknown"


@router.get("", response_model=List[ChannelMetadata])
async def list_channels() -> List[ChannelMetadata]:
    """List all channel metadata records."""
    storage = get_storage()
    try:
        return storage.channel_meta_list()
    except Exception as exc:
        logger.exception("channel_meta_list failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{channel_type}", response_model=ChannelMetadata)
async def get_channel(channel_type: str) -> ChannelMetadata:
    """Get metadata for a channel."""
    storage = get_storage()
    ct = _sanitize_channel_type(channel_type)
    record = storage.channel_meta_get(ct)
    if not record:
        raise HTTPException(status_code=404, detail=f"Channel not found: {channel_type!r}")
    return record


@router.put("/{channel_type}", response_model=ChannelMetadata)
async def put_channel(channel_type: str, body: ChannelMetadataCreate) -> ChannelMetadata:
    """Create or update channel metadata (display_name, description, config, metadata)."""
    storage = get_storage()
    ct = _sanitize_channel_type(channel_type)
    if not ct or ct == "unknown":
        raise HTTPException(status_code=400, detail="Invalid channel_type")
    try:
        return storage.channel_meta_set(ct, body)
    except Exception as exc:
        logger.exception("channel_meta_set failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{channel_type}", status_code=204)
async def delete_channel(channel_type: str) -> None:
    """Remove channel metadata."""
    storage = get_storage()
    ct = _sanitize_channel_type(channel_type)
    deleted = storage.channel_meta_delete(ct)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Channel not found: {channel_type!r}")
