from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional, List

from app.storage import get_storage
from app.models import DataMetadata, AccessUpdate
from app import config

router = APIRouter(prefix="/api/v1/data", tags=["Data"])


def _get_base_url(request: Request) -> str:
    """Derive the API base URL from config or the incoming request."""
    if config.API_BASE_URL:
        return config.API_BASE_URL.rstrip("/")
    return str(request.base_url).rstrip("/")


@router.get("/{data_id}/access")
async def get_access(
    data_id: str,
    owner_user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Get access control settings for a data item. Returns empty if not found."""
    storage = get_storage()

    try:
        metadata = storage.get_metadata(data_id, owner_user_id)
        if metadata is None:
            return {
                "data_id": data_id,
                "access": None
            }
        return {
            "data_id": data_id,
            "access": metadata.access
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{data_id}/access", response_model=DataMetadata)
async def update_access(
    data_id: str,
    access_update: AccessUpdate,
    request: Request,
    owner_user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """
    Update access control for a data item.

    Access control values:
    - `null`: Public access (everyone can access)
    - `["*"]`: All authenticated users
    - `["user:uuid"]`: Specific user by ID
    - `["role:name"]`: Users with specific role

    Multiple entries can be combined: `["user:abc", "role:admin"]`
    """
    storage = get_storage()

    try:
        metadata = storage.update_access(owner_user_id, data_id, access_update.access)
        base_url = _get_base_url(request)
        metadata.address = f"{base_url}/api/v1/data/{metadata.data_id}"
        return metadata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data not found: {data_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{data_id}/access/check")
async def check_access(
    data_id: str,
    owner_user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
    user_id: Optional[str] = Query(default=None, description="User ID to check access for"),
    role: Optional[str] = Query(default=None, description="Role to check access for"),
):
    """
    Check if a user has access to a data item. Returns false if data not found.
    """
    storage = get_storage()

    try:
        has_access = storage.check_access(owner_user_id, data_id, user_id=user_id, user_role=role)
        metadata = storage.get_metadata(data_id, owner_user_id)

        return {
            "data_id": data_id,
            "has_access": has_access,
            "access": metadata.access if metadata else None,
            "checked_user_id": user_id,
            "checked_role": role
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
