"""Statistics router for platform-wide and per-user analytics."""

from fastapi import APIRouter, HTTPException

from app.storage import get_storage
from app.models import (
    AgentTypeStats,
    DataStats,
    EmbeddingStats,
    GlobalStats,
    MemoryStats,
    PerUserStats,
    PerUserTokenStats,
    TokenUsageRecord,
    ViewpointStats,
)
from app import config

router = APIRouter(prefix="/api/v1/stats", tags=["Statistics"])


@router.get("", response_model=GlobalStats)
async def get_global_stats():
    """Return cached global statistics. Returns 404 if stats have not been computed yet."""
    storage = get_storage()
    storage._check_stats_enabled()

    stats = storage.get_global_stats()
    if stats is None:
        raise HTTPException(status_code=404, detail="Statistics not yet computed. Call POST /api/v1/stats/refresh first.")
    return stats


@router.get("/data", response_model=DataStats)
async def get_data_stats():
    """Return just the data statistics from cached global stats."""
    storage = get_storage()
    storage._check_stats_enabled()

    stats = storage.get_global_stats()
    if stats is None:
        raise HTTPException(status_code=404, detail="Statistics not yet computed. Call POST /api/v1/stats/refresh first.")
    return stats.data


@router.get("/memories", response_model=MemoryStats)
async def get_memory_stats():
    """Return just the memory statistics from cached global stats."""
    storage = get_storage()
    storage._check_stats_enabled()

    stats = storage.get_global_stats()
    if stats is None:
        raise HTTPException(status_code=404, detail="Statistics not yet computed. Call POST /api/v1/stats/refresh first.")
    return stats.memories


@router.get("/embeddings", response_model=EmbeddingStats)
async def get_embedding_stats():
    """Return just the embeddings statistics from cached global stats."""
    storage = get_storage()
    storage._check_stats_enabled()

    stats = storage.get_global_stats()
    if stats is None:
        raise HTTPException(status_code=404, detail="Statistics not yet computed. Call POST /api/v1/stats/refresh first.")
    return stats.embeddings


@router.get("/viewpoints", response_model=ViewpointStats)
async def get_viewpoint_stats():
    """Return just the viewpoints statistics from cached global stats."""
    storage = get_storage()
    storage._check_stats_enabled()

    stats = storage.get_global_stats()
    if stats is None:
        raise HTTPException(status_code=404, detail="Statistics not yet computed. Call POST /api/v1/stats/refresh first.")
    return stats.viewpoints


@router.get("/users/{user_id}", response_model=PerUserStats)
async def get_user_stats(user_id: str):
    """Return cached statistics for a specific user."""
    storage = get_storage()
    storage._check_stats_enabled()

    stats = storage.get_user_stats(user_id)
    if stats is None:
        raise HTTPException(status_code=404, detail=f"Statistics for user '{user_id}' not yet computed. Call POST /api/v1/stats/refresh/users/{user_id} first.")
    return stats


@router.post("/refresh", response_model=GlobalStats)
async def refresh_all_stats():
    """Force recompute all statistics (global + per-user)."""
    storage = get_storage()
    storage._check_stats_enabled()

    try:
        stats = storage.refresh_all_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh statistics: {str(e)}")


@router.post("/refresh/users/{user_id}", response_model=PerUserStats)
async def refresh_user_stats(user_id: str):
    """Force recompute statistics for a specific user."""
    storage = get_storage()
    storage._check_stats_enabled()

    try:
        stats = storage.compute_user_stats(user_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh user statistics: {str(e)}")


# =============================================================================
# Live agent-type counts (maintained by the webhook routing pipeline)
# =============================================================================

@router.get("/agent-types", response_model=AgentTypeStats)
async def get_agent_type_stats():
    """Return current live per-agent-type data counts.

    These counts are updated in real-time by the webhook sub-agent pipeline
    on every write and delete, unlike the batch-computed global stats.
    """
    storage = get_storage()
    storage._check_stats_enabled()
    return storage.get_agent_type_counts()


@router.post("/agent-types/{agent_type}/increment", response_model=AgentTypeStats)
async def increment_agent_type_count(agent_type: str):
    """Increment the count for the given agent type by 1.

    Called by the webhook sub-agent pipeline after each successful write.

    Args:
        agent_type: The agent type string (e.g. ``pdf``, ``lidar``).
    """
    storage = get_storage()
    storage._check_stats_enabled()
    try:
        return storage.update_agent_type_count(agent_type, delta=1)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to increment count: {exc}")


@router.post("/agent-types/{agent_type}/decrement", response_model=AgentTypeStats)
async def decrement_agent_type_count(agent_type: str):
    """Decrement the count for the given agent type by 1 (floor 0).

    Called by the webhook sub-agent pipeline when a data item is deleted.

    Args:
        agent_type: The agent type string (e.g. ``pdf``, ``lidar``).
    """
    storage = get_storage()
    storage._check_stats_enabled()
    try:
        return storage.update_agent_type_count(agent_type, delta=-1)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to decrement count: {exc}")


# =============================================================================
# Token usage tracking
# =============================================================================

@router.post("/token-usage", response_model=PerUserTokenStats)
async def record_token_usage(record: TokenUsageRecord):
    """Record a token usage event from the webhook agent pipeline.

    Accumulates prompt/completion/total tokens into the per-user
    ``token_usage.json`` stats file.
    """
    storage = get_storage()
    storage._check_stats_enabled()
    try:
        return storage.record_token_usage(record)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to record token usage: {exc}")


@router.get("/token-usage/{user_id}", response_model=PerUserTokenStats)
async def get_token_usage(user_id: str):
    """Return accumulated token usage statistics for a user."""
    storage = get_storage()
    storage._check_stats_enabled()
    return storage.get_token_usage(user_id)


@router.delete("/token-usage/{user_id}", response_model=PerUserTokenStats)
async def delete_token_usage(user_id: str):
    """Delete accumulated token usage statistics for a user, resetting all counters to zero."""
    storage = get_storage()
    storage._check_stats_enabled()
    try:
        return storage.delete_token_usage(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete token usage: {exc}")
