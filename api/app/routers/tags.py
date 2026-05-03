from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional, List
from pydantic import BaseModel

from app.storage import get_storage
from app.models import DataMetadata, DataListItem
from app import config


def _get_base_url(request: Request) -> str:
    """Derive the API base URL from config or the incoming request."""
    if config.API_BASE_URL:
        return config.API_BASE_URL.rstrip("/")
    return str(request.base_url).rstrip("/")


def _set_address(item, base_url: str) -> None:
    """Populate the address field on a DataMetadata or DataListItem."""
    item.address = f"{base_url}/api/v1/data/{item.data_id}"


class TagsUpdate(BaseModel):
    """Model for updating tags."""
    tags: Optional[List[str]] = None


class TagsAdd(BaseModel):
    """Model for adding tags."""
    tags: List[str]


class TagsRemove(BaseModel):
    """Model for removing tags."""
    tags: List[str]


router = APIRouter(prefix="/api/v1", tags=["Tags"])


# =========================================================================
# Per-Data Tags Endpoints
# =========================================================================

@router.get("/data/{data_id}/tags")
async def get_tags(
    data_id: str,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Get tags for a data item. Returns empty if not found."""
    storage = get_storage()

    try:
        metadata = storage.get_metadata(data_id, user_id)
        if metadata is None:
            return {
                "data_id": data_id,
                "tags": None
            }
        return {
            "data_id": data_id,
            "tags": metadata.tags
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/data/{data_id}/tags", response_model=DataMetadata)
async def update_tags(
    data_id: str,
    tags_update: TagsUpdate,
    request: Request,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """
    Update tags for a data item (replaces all existing tags).

    Pass `null` or empty array to clear all tags.
    Tags are automatically deduplicated.
    """
    storage = get_storage()

    try:
        metadata = storage.update_tags(user_id, data_id, tags_update.tags)
        _set_address(metadata, _get_base_url(request))
        return metadata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data not found: {data_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/{data_id}/tags/add", response_model=DataMetadata)
async def add_tags(
    data_id: str,
    tags_add: TagsAdd,
    request: Request,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """
    Add tags to a data item (merges with existing tags).

    Duplicate tags are automatically handled.
    """
    storage = get_storage()

    try:
        metadata = storage.add_tags(user_id, data_id, tags_add.tags)
        _set_address(metadata, _get_base_url(request))
        return metadata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data not found: {data_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/{data_id}/tags/remove", response_model=DataMetadata)
async def remove_tags(
    data_id: str,
    tags_remove: TagsRemove,
    request: Request,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """
    Remove specific tags from a data item.

    Tags not present on the item are silently ignored.
    """
    storage = get_storage()

    try:
        metadata = storage.remove_tags(user_id, data_id, tags_remove.tags)
        _set_address(metadata, _get_base_url(request))
        return metadata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data not found: {data_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Search & Discovery Endpoints
# =========================================================================

@router.get("/tags", response_model=List[str])
async def list_all_tags():
    """
    Get all unique tags used across all data items.
    
    Returns a sorted list of all tags in the system.
    """
    storage = get_storage()
    
    try:
        tags = storage.get_all_tags()
        return tags
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tags/search", response_model=List[DataListItem])
async def search_by_tags(
    request: Request,
    tags: str = Query(..., description="Comma-separated list of tags to search for"),
    match_all: bool = Query(default=False, description="If true, items must have ALL tags. If false, items must have ANY tag."),
    user_id: Optional[str] = Query(default=None, description="User ID for access filtering"),
    role: Optional[str] = Query(default=None, description="Role for access filtering")
):
    """
    Search data items by tags.
    
    - `tags`: Comma-separated list of tags to search for (e.g., "important,work,project-x")
    - `match_all`: 
      - `false` (default): Returns items that have ANY of the specified tags (OR logic)
      - `true`: Returns items that have ALL of the specified tags (AND logic)
    - `user_id`, `role`: Optional access filtering
    
    Examples:
    - `/api/v1/tags/search?tags=important` - Find items with "important" tag
    - `/api/v1/tags/search?tags=work,personal&match_all=false` - Find items with "work" OR "personal"
    - `/api/v1/tags/search?tags=work,urgent&match_all=true` - Find items with BOTH "work" AND "urgent"
    """
    storage = get_storage()
    
    try:
        # Parse comma-separated tags
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        
        if not tag_list:
            raise HTTPException(status_code=400, detail="At least one tag must be provided")
        
        items = storage.search_by_tags(
            tags=tag_list,
            match_all=match_all,
            user_id=user_id,
            user_role=role
        )
        base_url = _get_base_url(request)
        for item in items:
            _set_address(item, base_url)
        return items
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
