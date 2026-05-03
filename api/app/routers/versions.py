from fastapi import APIRouter, HTTPException, Query
from typing import List

from app.storage import get_storage
from app.models import VersionInfo, DataMetadata
from app import config

router = APIRouter(prefix="/api/v1/versions", tags=["versions"])


@router.get("/{data_id}")
async def get_versions(
    data_id: str,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Get all versions for a data item. Returns empty list if not found."""
    storage = get_storage()

    try:
        metadata = storage.get_metadata(data_id, user_id)
        if metadata is None:
            return []
        return metadata.versions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{data_id}/{version}")
async def get_specific_version(
    data_id: str,
    version: int,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Get a specific version of data. Returns empty if not found."""
    from fastapi.responses import Response
    storage = get_storage()

    try:
        result = storage.get_raw_data(data_id, user_id, version)
        if result is None:
            return Response(content=b"", media_type="application/octet-stream")
        content, content_type = result
        return Response(content=content, media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
