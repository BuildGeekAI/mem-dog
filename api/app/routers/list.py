"""User data listing router.

Lists data items for a user across their memories, with multiple
output formats (meta or raw).
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Dict, Optional
from enum import Enum

from app.storage import get_storage
from app.models import (
    DataMetadata,
    DataListItem,
    UserDataItem,
    UserListResponse,
    PaginationInfo,
    MemoryDataEntry,
)
from app import config

logger = logging.getLogger("mem_dog.routers.list")

# Pagination defaults
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _get_base_url(request: Request) -> str:
    """Derive the API base URL from config or the incoming request."""
    if config.API_BASE_URL:
        return config.API_BASE_URL.rstrip("/")
    return str(request.base_url).rstrip("/")


router = APIRouter(prefix="/api/v1/list", tags=["list"])


class ListFormat(str, Enum):
    meta = "meta"
    raw = "raw"


@router.get("", response_model=UserListResponse)
async def list_user_data(
    request: Request,
    user: str = Query(default=config.DEFAULT_USER_ID, description="User identifier"),
    format: ListFormat = Query(default=ListFormat.meta, description="Response format: meta or raw"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum number of items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
):
    """Get data for a user in different formats with pagination.

    Data is collected across all memories owned by the user.

    - **meta**: Returns metadata for all data items owned by user. Each item includes an ``address`` field.
    - **raw**: Returns raw data content for all items (base64 encoded for binary). Each item includes an ``address`` field.

    Pagination:
    - **limit**: Maximum items per page (1-100, default 20)
    - **offset**: Number of items to skip (default 0)
    """
    storage = get_storage()
    base_url = _get_base_url(request)

    try:
        # Collect all data_ids from the user's memories
        user_memories, _ = storage.list_memories(user_id=user, limit=10000)
        unique_data_ids: List[str] = []
        seen: set = set()
        for mem in user_memories:
            for did in mem.data_ids:
                if did not in seen:
                    seen.add(did)
                    unique_data_ids.append(did)

        if not unique_data_ids:
            return UserListResponse(
                user=user,
                format=format.value,
                count=0,
                items=[],
                pagination=PaginationInfo(
                    total=0,
                    limit=limit,
                    offset=offset,
                    has_more=False,
                ),
            )

        if format == ListFormat.meta:
            return await _get_meta_format(user, unique_data_ids, limit, offset, base_url)
        elif format == ListFormat.raw:
            return await _get_raw_format(user, unique_data_ids, limit, offset, base_url)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _get_meta_format(
    user: str,
    data_ids: List[str],
    limit: int,
    offset: int,
    base_url: str = "",
) -> UserListResponse:
    """Return metadata format with full metadata for each data item."""
    storage = get_storage()

    items = []
    for data_id in data_ids:
        try:
            metadata = storage.get_metadata(data_id, user)
            if metadata is None:
                continue

            latest_version = metadata.versions[-1] if metadata.versions else None

            item = UserDataItem(
                data_id=metadata.data_id,
                current_version=metadata.current_version,
                created_at=metadata.created_at,
                updated_at=metadata.updated_at,
                content_type=latest_version.content_type if latest_version else "unknown",
                size=latest_version.size if latest_version else 0,
            )
            item_dict = item.model_dump()
            if base_url:
                item_dict["address"] = f"{base_url}/api/v1/data/{data_id}"
            items.append(item_dict)
        except Exception as e:
            logger.warning("Failed to load metadata for list item", extra={"data_id": data_id, "error": str(e)})
            continue

    items.sort(key=lambda x: x["updated_at"], reverse=True)

    total = len(items)
    paginated_items = items[offset : offset + limit]
    has_more = (offset + limit) < total

    return UserListResponse(
        user=user,
        format="meta",
        count=len(paginated_items),
        items=paginated_items,
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ),
    )


async def _get_raw_format(
    user: str,
    data_ids: List[str],
    limit: int,
    offset: int,
    base_url: str = "",
) -> UserListResponse:
    """Return raw format with actual data content (base64 for binary)."""
    storage = get_storage()
    import base64

    items = []
    for data_id in data_ids:
        try:
            metadata = storage.get_metadata(data_id, user)
            if metadata is None:
                continue

            result = storage.get_raw_data(data_id, user)
            if result is None:
                continue
            content, content_type = result

            if content_type.startswith("text/") or content_type == "application/json":
                try:
                    content_data = content.decode("utf-8")
                    if content_type == "application/json":
                        try:
                            content_data = json.loads(content_data)
                        except json.JSONDecodeError:
                            pass
                    encoding = "utf-8"
                except UnicodeDecodeError:
                    content_data = base64.b64encode(content).decode("ascii")
                    encoding = "base64"
            else:
                content_data = base64.b64encode(content).decode("ascii")
                encoding = "base64"

            item = {
                "data_id": data_id,
                "version": metadata.current_version,
                "content_type": content_type,
                "size": len(content),
                "encoding": encoding,
                "content": content_data,
                "updated_at": metadata.updated_at,
            }
            if base_url:
                item["address"] = f"{base_url}/api/v1/data/{data_id}"
            items.append(item)
        except Exception as e:
            logger.warning("Failed to load raw data for list item", extra={"data_id": data_id, "error": str(e)})
            continue

    items.sort(key=lambda x: x["updated_at"], reverse=True)

    total = len(items)
    paginated_items = items[offset : offset + limit]
    has_more = (offset + limit) < total

    return UserListResponse(
        user=user,
        format="raw",
        count=len(paginated_items),
        items=paginated_items,
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ),
    )


@router.get("/{data_id}")
async def get_user_data_item(
    data_id: str,
    request: Request,
    user: str = Query(default=config.DEFAULT_USER_ID, description="User identifier"),
    format: ListFormat = Query(default=ListFormat.meta, description="Response format"),
):
    """Get a specific data item for a user in the requested format.

    - **meta**: Returns full metadata with address
    - **raw**: Returns raw content with address
    """
    storage = get_storage()
    base_url = _get_base_url(request)

    try:
        # Verify user owns this data by checking their memories
        user_memories, _ = storage.list_memories(user_id=user, limit=10000)
        user_data_ids = set()
        for mem in user_memories:
            user_data_ids.update(mem.data_ids)

        if data_id not in user_data_ids:
            return {
                "user": user,
                "data_id": data_id,
                "format": format.value,
                "metadata": None,
                "content": None,
            }

        if format == ListFormat.meta:
            metadata = storage.get_metadata(data_id, user)
            if metadata is None:
                return {
                    "user": user,
                    "data_id": data_id,
                    "format": "meta",
                    "metadata": None,
                }
            metadata.address = f"{base_url}/api/v1/data/{metadata.data_id}"
            return {
                "user": user,
                "data_id": data_id,
                "format": "meta",
                "metadata": metadata.model_dump(),
            }

        elif format == ListFormat.raw:
            import base64

            result = storage.get_raw_data(data_id, user)
            if result is None:
                return {
                    "user": user,
                    "data_id": data_id,
                    "format": "raw",
                    "content_type": None,
                    "size": 0,
                    "encoding": None,
                    "content": None,
                }
            content, content_type = result

            if content_type.startswith("text/") or content_type == "application/json":
                try:
                    content_data = content.decode("utf-8")
                    if content_type == "application/json":
                        try:
                            content_data = json.loads(content_data)
                        except json.JSONDecodeError:
                            pass
                    encoding = "utf-8"
                except UnicodeDecodeError:
                    content_data = base64.b64encode(content).decode("ascii")
                    encoding = "base64"
            else:
                content_data = base64.b64encode(content).decode("ascii")
                encoding = "base64"

            return {
                "user": user,
                "data_id": data_id,
                "format": "raw",
                "content_type": content_type,
                "size": len(content),
                "encoding": encoding,
                "content": content_data,
                "address": f"{base_url}/api/v1/data/{data_id}",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
