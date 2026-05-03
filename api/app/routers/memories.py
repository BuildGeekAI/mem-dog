"""Memory management router.

Provides CRUD for memories (the unified context container that replaces
the old timeline and session stores) and data-association endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional

from app.storage import get_storage
from app.models import (
    Memory,
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemoryListResponse,
    MemoryAddDataRequest,
    MemoryDataEntry,
    MemoryDataDeleteResponse,
    MemoryType,
    MemoryDuration,
    MemoryCategory,
    MEMORY_TYPE_CATEGORY,
    BulkMemoryDeleteRequest,
    BulkMemoryDeleteResponse,
    DataListItem,
    CompressMemoryRequest,
    CompressMemoryResponse,
)
from app import config

logger = logging.getLogger("mem_dog.routers.memories")


def _resolve_user_id(request: Request, user_id: str) -> str:
    """Use JWT-authenticated user_id when caller passed the default placeholder."""
    if user_id == config.DEFAULT_USER_ID:
        jwt_uid = getattr(request.state, "user_id", None)
        if jwt_uid:
            return jwt_uid
    return user_id

router = APIRouter(prefix="/api/v1/memories", tags=["Memories"])


def _memory_to_response(memory: Memory) -> MemoryResponse:
    """Convert a stored Memory to a MemoryResponse."""
    # Backward compat: derive category for old memories missing the field
    category = getattr(memory, "category", None)
    if not category:
        cat = MEMORY_TYPE_CATEGORY.get(memory.memory_type, "user")
        category = cat.value if hasattr(cat, 'value') else str(cat)
    return MemoryResponse(
        memory_id=memory.memory_id,
        memory_type=memory.memory_type,
        duration=memory.duration,
        category=category,
        name=memory.name,
        description=memory.description,
        user_id=memory.user_id,
        sub_type=getattr(memory, "sub_type", None),
        data_count=len(memory.data_ids),
        data_ids=memory.data_ids,
        metadata=memory.metadata,
        access_level=getattr(memory, "access_level", "private") or "private",
        shared_with=getattr(memory, "shared_with", []) or [],
        device_id=memory.device_id,
        device_info=memory.device_info,
        active=memory.active,
        expires_at=memory.expires_at,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        org_id=getattr(memory, "org_id", None),
        project_id=getattr(memory, "project_id", None),
    )


# =========================================================================
# Memory CRUD
# =========================================================================


@router.post("", response_model=MemoryResponse, status_code=201)
async def create_memory(memory_create: MemoryCreate):
    """Create a new memory container.

    Specify the memory type (timeline, session, conversation, user,
    organizational, factual, episodic, semantic) along with a name and
    the owning user_id.  An optional ``memory_id`` can be provided to
    give the memory a stable, caller-chosen identifier; if omitted a
    An ID is generated automatically if omitted.  Session-type memories accept
    optional device_id, device_info, and ttl_hours fields.
    """
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.create_memory(
            memory_create,
            memory_id_override=memory_create.memory_id,
        )
        return _memory_to_response(memory)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create memory")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    user_id: Optional[str] = Query(default=None, description="Filter by user"),
    memory_type: Optional[MemoryType] = Query(default=None, description="Filter by memory type"),
    duration: Optional[MemoryDuration] = Query(default=None, description="Filter by duration (short_term/long_term)"),
    active: Optional[bool] = Query(default=None, description="Filter session memories by active status"),
    sub_type: Optional[str] = Query(default=None, description="Filter by sub_type (e.g. legal, hr, customer)"),
    access_level: Optional[str] = Query(default=None, description="Filter by access level (private/shared/public/restricted)"),
    category: Optional[str] = Query(default=None, description="Filter by Mem0 category (conversation/session/user/organizational)"),
    include_expired: bool = Query(default=False, description="Include expired memories in results"),
    project_id: Optional[str] = Query(default=None, description="Scope results to a specific project"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=1000),
):
    """List memories with optional filters.

    Use query parameters to narrow results by user, type, duration,
    sub_type, category, access level, or active status.
    Expired memories are hidden by default; set include_expired=true to include them.
    """
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memories, total = storage.list_memories(
            user_id=user_id,
            memory_type=memory_type,
            duration=duration,
            active=active,
            sub_type=sub_type,
            access_level=access_level,
            category=category,
            include_expired=include_expired,
            project_id=project_id,
            skip=skip,
            limit=limit,
        )
        return MemoryListResponse(
            items=[_memory_to_response(m) for m in memories],
            total=total,
            skip=skip,
            limit=limit,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to list memories")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the memory owner"),
):
    """Get a memory by ID. Returns 404 if not found."""
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.get_memory(memory_id, user_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        return _memory_to_response(memory)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to get memory", extra={"memory_id": memory_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str, 
    memory_update: MemoryUpdate,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the memory owner"),
):
    """Update a memory's metadata, name, description, or session-specific fields."""
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.update_memory(memory_id, memory_update, user_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        return _memory_to_response(memory)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update memory", extra={"memory_id": memory_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str, 
    delete_data: bool = Query(default=False, description="Also delete all associated data items"),
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the memory owner"),
):
    """Delete a memory.

    By default only the memory container and its data associations are
    removed.  Set ``delete_data=true`` to also permanently delete all
    data items that belong to this memory.
    """
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.get_memory(memory_id, user_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

        deleted_data_count = 0
        if delete_data and memory.data_ids:
            deleted_ids, _ = storage.delete_memory_data(memory_id, user_id)
            deleted_data_count = len(deleted_ids)

        storage.delete_memory(memory_id, user_id)

        msg = f"Memory '{memory_id}' deleted"
        if delete_data:
            msg += f" along with {deleted_data_count} data items"

        return {"memory_id": memory_id, "deleted": True, "deleted_data_count": deleted_data_count, "message": msg}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to delete memory", extra={"memory_id": memory_id})
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Data Association
# =========================================================================


@router.post("/{memory_id}/data", response_model=MemoryResponse)
async def add_data_to_memory(
    memory_id: str, 
    request: MemoryAddDataRequest,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the memory owner"),
):
    """Add one or more data items to a memory.

    The data items must already exist in the data store.  This creates
    a many-to-many link between each data item and the memory.
    """
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.get_memory(memory_id, user_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

        for data_id in request.data_ids:
            metadata = storage.get_metadata(data_id, user_id)
            if metadata is None:
                raise HTTPException(status_code=404, detail=f"Data not found: {data_id}")
            storage.add_data_to_memory(
                memory_id, data_id, entry_metadata=request.metadata or {}, user_id=user_id
            )

        # Re-read updated memory
        memory = storage.get_memory(memory_id, user_id)
        return _memory_to_response(memory)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to add data to memory", extra={"memory_id": memory_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}/data")
async def get_memory_data(
    memory_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=1000),
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the memory owner"),
):
    """List data items associated with a memory (paginated)."""
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.get_memory(memory_id, user_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

        items, total = storage.get_memory_data(memory_id, user_id=user_id, skip=skip, limit=limit)
        return {
            "memory_id": memory_id,
            "items": [item.model_dump() for item in items],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to get memory data", extra={"memory_id": memory_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}/entries")
async def get_memory_entries(
    memory_id: str,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the memory owner"),
):
    """Get raw MemoryDataEntry records for a memory.

    Unlike ``/data`` which returns full DataListItem objects, this
    endpoint returns the lightweight association entries which include
    action and version fields (useful for timeline-type memories).
    """
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.get_memory(memory_id, user_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

        entries = storage.get_memory_data_entries(memory_id, user_id)
        return {
            "memory_id": memory_id,
            "entries": [e.model_dump() for e in entries],
            "total": len(entries),
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to get memory entries", extra={"memory_id": memory_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}/data/{data_id}")
async def remove_data_from_memory(
    memory_id: str, 
    data_id: str,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the memory owner"),
):
    """Remove a data item from a memory (the data itself is not deleted)."""
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.get_memory(memory_id, user_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

        storage.remove_data_from_memory(memory_id, data_id, user_id)
        return {"memory_id": memory_id, "data_id": data_id, "message": "Data removed from memory"}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to remove data from memory", extra={"memory_id": memory_id, "data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Bulk Operations
# =========================================================================


@router.post("/bulk/delete", response_model=BulkMemoryDeleteResponse)
async def bulk_delete_memories(request: BulkMemoryDeleteRequest):
    """Delete multiple memories, with optional data cleanup.

    Provide memory_ids, or filter by user_id / memory_type.
    Set delete_data=true to also permanently delete associated data items.
    """
    storage = get_storage()
    storage._check_memories_enabled()

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


# ---------------------------------------------------------------------------
# Compression
# ---------------------------------------------------------------------------

import os
AUTO_COMPRESS_THRESHOLD = int(os.environ.get("AUTO_COMPRESS_THRESHOLD", "50"))


@router.post("/{memory_id}/compress", response_model=CompressMemoryResponse)
async def compress_memory(
    memory_id: str,
    request: CompressMemoryRequest = CompressMemoryRequest(),
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the memory owner"),
):
    """Compress a memory's data items into a single summary.

    Uses LLM to summarize all content in the memory into a structured summary
    stored as a new data item with tag ``compressed:true``.

    If ``archive_originals=true``, original items get tagged ``archived:true``
    and unlinked from the memory.
    """
    storage = get_storage()
    storage._check_memories_enabled()

    try:
        memory = storage.get_memory(memory_id, user_id)
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

        if not memory.data_ids:
            raise HTTPException(status_code=400, detail="Memory has no data items to compress")

        # Gather all content
        content_parts: list[str] = []
        for data_id in memory.data_ids:
            try:
                raw = storage.get_data(data_id, user_id=user_id)
                if raw:
                    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                    content_parts.append(f"--- Item {data_id} ---\n{text[:2000]}")
            except Exception:
                pass

        if not content_parts:
            raise HTTPException(status_code=400, detail="Could not read any data items")

        combined = "\n\n".join(content_parts)

        # LLM summarization
        from app.routers.ai_query import _chat_completion
        messages = [
            {"role": "system", "content": (
                "You are a memory compression assistant. Summarize the following content "
                "into a concise, structured summary. Include: key facts, important entities, "
                "timeline of events, action items, and decisions made. "
                f"Keep the summary under {request.max_summary_length} characters."
            )},
            {"role": "user", "content": combined},
        ]
        result = await _chat_completion(messages, max_tokens=1024, temperature=0.3)
        summary = result["choices"][0]["message"]["content"].strip()

        # Store summary as new data item
        from ulid import ULID
        summary_data_id = f"data_{ULID()}"
        storage.store_data(
            summary_data_id, summary.encode("utf-8"),
            name=f"compressed-summary-{memory_id}",
            user_id=user_id,
        )
        # Tag as compressed
        storage.add_tags(summary_data_id, ["compressed:true", f"source_memory:{memory_id}"], user_id=user_id)
        # Link to memory
        storage.add_data_to_memory(memory_id, summary_data_id, user_id=user_id)

        archived = False
        if request.archive_originals:
            for data_id in memory.data_ids:
                if data_id == summary_data_id:
                    continue
                try:
                    storage.add_tags(data_id, ["archived:true"], user_id=user_id)
                    storage.remove_data_from_memory(memory_id, data_id, user_id=user_id)
                except Exception:
                    pass
            archived = True

        return CompressMemoryResponse(
            memory_id=memory_id,
            summary_data_id=summary_data_id,
            original_count=len(memory.data_ids),
            summary_length=len(summary),
            archived=archived,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compress memory", extra={"memory_id": memory_id})
        raise HTTPException(status_code=500, detail=str(e))
