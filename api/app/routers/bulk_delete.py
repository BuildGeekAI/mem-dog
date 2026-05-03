"""Bulk delete operations for data items and memories."""

import logging

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.storage import get_storage
from app.models import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    UserDataDeleteResponse,
    MemoryDataDeleteResponse,
    BulkMemoryDeleteRequest,
    BulkMemoryDeleteResponse,
)
from app import config

logger = logging.getLogger("mem_dog.routers.bulk_delete")

router = APIRouter(prefix="/api/v1/bulk", tags=["Bulk Delete"])


# =============================================================================
# Data Bulk Delete Endpoints
# =============================================================================


@router.post("/data/delete", response_model=BulkDeleteResponse)
async def bulk_delete_data(request: BulkDeleteRequest):
    """Delete multiple data items by their IDs.

    Each item and all its versions will be permanently removed.
    Data is also removed from any associated memories.

    Returns a summary of deleted and failed items.
    """
    storage = get_storage()

    try:
        user_id = (request.user_id or "").strip() or config.DEFAULT_USER_ID
        # Clean up memory references before deleting
        for data_id in request.data_ids:
            try:
                metadata = storage.get_metadata(data_id, user_id)
                if metadata is not None and metadata.memory_ids and config.is_memories_enabled():
                    for mid in metadata.memory_ids:
                        try:
                            storage.remove_data_from_memory(mid, data_id, user_id=user_id)
                        except Exception:
                            pass
            except Exception:
                pass

        deleted_ids, failed_ids = storage.delete_bulk_data(request.data_ids, user_id)

        return BulkDeleteResponse(
            deleted_count=len(deleted_ids),
            failed_count=len(failed_ids),
            deleted_ids=deleted_ids,
            failed_ids=failed_ids,
            message=f"Bulk delete completed: {len(deleted_ids)} deleted, {len(failed_ids)} failed",
        )
    except Exception as e:
        logger.exception("Failed to bulk delete data")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/data/user/{user}", response_model=UserDataDeleteResponse)
async def delete_all_user_data(user: str):
    """Delete ALL data items for a specific user.

    This permanently removes all data items found across the user's
    memories and deletes those memories as well.

    **WARNING**: This action is irreversible and deletes all versions of all data.
    """
    storage = get_storage()

    try:
        deleted_count = storage.delete_all_user_data(user)

        return UserDataDeleteResponse(
            user=user,
            deleted_count=deleted_count,
            message=f"All data for user '{user}' deleted: {deleted_count} items removed",
        )
    except Exception as e:
        logger.exception("Failed to delete all user data", extra={"user": user})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/data/memory/{memory_id}", response_model=MemoryDataDeleteResponse
)
async def delete_memory_data(
    memory_id: str,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID who owns this memory"),
):
    """Delete all data items associated with a specific memory.

    This permanently removes all data items linked to the memory.
    The memory itself remains but with an empty data list.

    **WARNING**: This action is irreversible.
    """
    storage = get_storage()

    try:
        memory = storage.get_memory(memory_id, user_id)
        if not memory:
            raise HTTPException(
                status_code=404, detail=f"Memory not found: {memory_id}"
            )

        deleted_ids, failed_ids = storage.delete_memory_data(memory_id, user_id)

        return MemoryDataDeleteResponse(
            memory_id=memory_id,
            deleted_count=len(deleted_ids),
            failed_count=len(failed_ids),
            deleted_ids=deleted_ids,
            message=f"Memory data deleted: {len(deleted_ids)} items removed, {len(failed_ids)} failed",
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(
            "Failed to delete memory data", extra={"memory_id": memory_id}
        )
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Memory Bulk Delete Endpoints
# =============================================================================


@router.post("/memories/delete", response_model=BulkMemoryDeleteResponse)
async def bulk_delete_memories(request: BulkMemoryDeleteRequest):
    """Delete multiple memories, with optional data cleanup.

    Options:
    - **memory_ids**: Delete specific memories by ID
    - **user_id**: Delete all memories for a specific user
    - **memory_type**: Delete all memories of a specific type
    - **delete_data**: Also delete all data items associated with the memories

    **WARNING**: When delete_data is true, all associated data is permanently removed.
    """
    storage = get_storage()

    try:
        deleted_memories, deleted_data = storage.delete_bulk_memories(
            memory_ids=request.memory_ids,
            user_id=request.user_id,
            memory_type=request.memory_type,
            delete_data=request.delete_data,
        )

        parts = [f"{deleted_memories} memories deleted"]
        if request.delete_data:
            parts.append(f"{deleted_data} data items deleted")

        return BulkMemoryDeleteResponse(
            deleted_memories=deleted_memories,
            deleted_data_items=deleted_data,
            message=", ".join(parts),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to bulk delete memories")
        raise HTTPException(status_code=500, detail=str(e))
