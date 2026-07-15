"""Graph memory router — entity/relationship CRUD and search."""

import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from app.storage import get_storage
from app.models import (
    Entity, EntityCreate, EntityBatchRequest, EntityBatchResponse,
    Relationship, RelationshipCreate, GraphSearchResult,
)

logger = logging.getLogger("mem_dog.routers.graph")

router = APIRouter(prefix="/api/v1/graph", tags=["Graph Memory"])


@router.get("/entities", response_model=List[GraphSearchResult])
async def search_entities(
    q: str = Query(..., description="Search query text"),
    user_id: str = Query(default="", description="User ID"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
    limit: int = Query(default=20, le=100),
):
    """Search entities by name substring."""
    storage = get_storage()
    uid = user_id.strip() or "default"
    results = storage.search_entities(q, uid, entity_type=entity_type, limit=limit)
    return results


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    user_id: str = Query(default="", description="User ID"),
):
    """Get a single entity by ID."""
    storage = get_storage()
    uid = user_id.strip() or "default"
    entity = storage.get_entity(entity_id, uid)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/entities/{entity_id}/relationships")
async def get_entity_relationships(
    entity_id: str,
    user_id: str = Query(default="", description="User ID"),
):
    """Get all relationships for an entity (as source or target)."""
    storage = get_storage()
    uid = user_id.strip() or "default"
    return storage.get_entity_relationships(entity_id, uid)


@router.get("/data/{data_id}/entities")
async def get_data_entities(
    data_id: str,
    user_id: str = Query(default="", description="User ID"),
):
    """Get all entities extracted from a specific data item."""
    storage = get_storage()
    uid = user_id.strip() or "default"
    return storage.get_data_entities(data_id, uid)


@router.post("/entities/batch", response_model=EntityBatchResponse)
async def batch_create_entities(req: EntityBatchRequest):
    """Batch create entities and relationships for a data item.

    Used by the webhook pipeline after LLM entity extraction.
    """
    storage = get_storage()
    entity_ids: List[str] = []
    name_to_id: dict = {}

    for ec in req.entities:
        result = storage.upsert_entity(
            data_id=req.data_id,
            user_id=req.user_id,
            entity_type=ec.entity_type,
            entity_name=ec.entity_name,
            confidence=ec.confidence,
            metadata=ec.metadata or {},
        )
        if result:
            eid = result.get("entity_id", "")
            entity_ids.append(eid)
            name_to_id[ec.entity_name.strip().lower()] = eid

    rels_created = 0
    for rc in req.relationships:
        src_id = name_to_id.get(rc.source.strip().lower())
        tgt_id = name_to_id.get(rc.target.strip().lower())
        if src_id and tgt_id:
            result = storage.create_relationship(
                user_id=req.user_id,
                data_id=req.data_id,
                source_entity_id=src_id,
                target_entity_id=tgt_id,
                rel_type=rc.rel_type,
                strength=rc.strength,
                description=rc.description,
            )
            if result:
                rels_created += 1

    # Fire-and-forget: also ingest to Graphiti knowledge graph
    asyncio.create_task(_ingest_to_graphiti(req.data_id, req.user_id, req.entities, req.relationships))

    return EntityBatchResponse(
        entities_created=len(entity_ids),
        relationships_created=rels_created,
        entity_ids=entity_ids,
    )


async def _ingest_to_graphiti(
    data_id: str, user_id: str,
    entities: List[EntityCreate], relationships: List[RelationshipCreate],
):
    """Feed extracted entities/relationships to Graphiti as an episode (non-blocking)."""
    try:
        from app.graphiti_client import is_graphiti_enabled, get_graphiti
        if not is_graphiti_enabled():
            return

        graphiti = await get_graphiti()
        if graphiti is None:
            return

        # Build episode body from entity names and relationship descriptions
        parts = [f"{e.entity_name} ({e.entity_type})" for e in entities]
        for r in relationships:
            desc = f"{r.source} {r.rel_type} {r.target}"
            if r.description:
                desc += f": {r.description}"
            parts.append(desc)

        episode_body = ". ".join(parts) if parts else data_id

        from graphiti_core.nodes import EpisodeType
        await graphiti.add_episode(
            name=data_id,
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description=f"mem-dog-entity-extraction (user:{user_id})",
            reference_time=datetime.now(timezone.utc),
        )
        logger.info("Graphiti episode created for data_id=%s (%d entities, %d rels)",
                     data_id, len(entities), len(relationships))
    except Exception as exc:
        logger.warning("Graphiti ingest failed for data_id=%s: %s", data_id, exc)


@router.delete("/entities/{entity_id}")
async def delete_entity(
    entity_id: str,
    user_id: str = Query(default="", description="User ID"),
):
    """Delete an entity and its relationships."""
    storage = get_storage()
    uid = user_id.strip() or "default"
    entity = storage.get_entity(entity_id, uid)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    # Delete by data_id cascades; for single entity we delete directly
    try:
        storage._supa_client.table("mem_dog_entities").delete().eq(
            "entity_id", entity_id
        ).eq("user_id", uid).execute()
    except Exception:
        # Fallback for non-Supabase backends
        pass
    return {"deleted": True, "entity_id": entity_id}


@router.delete("/data/{data_id}/entities")
async def delete_data_entities(
    data_id: str,
    user_id: str = Query(default="", description="User ID"),
):
    """Delete all entities extracted from a data item."""
    storage = get_storage()
    uid = user_id.strip() or "default"
    count = storage.delete_data_entities(data_id, uid)
    return {"deleted": count, "data_id": data_id}


# ---------------------------------------------------------------------------
# Temporal graph endpoints (Graphiti-powered)
# ---------------------------------------------------------------------------


class FactResult(BaseModel):
    fact: str
    source_entity: str | None = None
    target_entity: str | None = None
    valid_at: str | None = None
    invalid_at: str | None = None
    episode_name: str | None = None


@router.get("/facts", response_model=List[FactResult])
async def query_facts(
    q: str = Query("", description="Search query for facts"),
    entity_id: str = Query("", description="Filter by entity ID"),
    at: str = Query("", description="ISO datetime — return facts valid at this point in time"),
    limit: int = Query(default=10, le=50),
):
    """Query temporal facts from the Graphiti knowledge graph.

    Supports point-in-time queries (``at`` parameter) to see what was known
    at a specific moment.
    """
    from app.graphiti_client import is_graphiti_enabled
    if not is_graphiti_enabled():
        raise HTTPException(status_code=400, detail="Graph search requires NEO4J_URI to be configured")

    search_query = q or entity_id or "recent facts"

    try:
        from app.graphiti_client import build_valid_at_search_filter, search_edges

        search_filter = None
        if at:
            search_filter = build_valid_at_search_filter(datetime.fromisoformat(at))

        results = await search_edges(
            search_query, limit=limit, search_filter=search_filter
        )

        facts = []
        for edge in results:
            facts.append(FactResult(
                fact=getattr(edge, "fact", "") or str(edge),
                source_entity=getattr(edge, "source_node_name", None)
                or getattr(edge, "source_node_uuid", None),
                target_entity=getattr(edge, "target_node_name", None)
                or getattr(edge, "target_node_uuid", None),
                valid_at=str(getattr(edge, "valid_at", "")) if getattr(edge, "valid_at", None) else None,
                invalid_at=str(getattr(edge, "invalid_at", "")) if getattr(edge, "invalid_at", None) else None,
                episode_name=getattr(edge, "episode_name", None) or getattr(edge, "name", None),
            ))
        return facts
    except Exception as exc:
        logger.warning("Graphiti facts query failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Graph query failed: {exc}")


@router.get("/facts/timeline", response_model=List[FactResult])
async def fact_timeline(
    entity_id: str = Query("", description="Entity ID or name to get timeline for"),
    limit: int = Query(default=20, le=100),
):
    """Get the fact history/timeline for an entity from the knowledge graph."""
    from app.graphiti_client import is_graphiti_enabled
    if not is_graphiti_enabled():
        raise HTTPException(status_code=400, detail="Graph search requires NEO4J_URI to be configured")

    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id is required")

    try:
        from app.graphiti_client import search_edges

        results = await search_edges(entity_id, limit=limit)

        facts = []
        for edge in results:
            facts.append(FactResult(
                fact=getattr(edge, "fact", "") or str(edge),
                source_entity=getattr(edge, "source_node_name", None)
                or getattr(edge, "source_node_uuid", None),
                target_entity=getattr(edge, "target_node_name", None)
                or getattr(edge, "target_node_uuid", None),
                valid_at=str(getattr(edge, "valid_at", "")) if getattr(edge, "valid_at", None) else None,
                invalid_at=str(getattr(edge, "invalid_at", "")) if getattr(edge, "invalid_at", None) else None,
                episode_name=getattr(edge, "episode_name", None) or getattr(edge, "name", None),
            ))
        return facts
    except Exception as exc:
        logger.warning("Graphiti timeline query failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Graph timeline query failed: {exc}")
