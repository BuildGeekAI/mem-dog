"""Universal Data Envelope ingestion endpoint (Plan 3).

``POST /api/v1/ingest`` accepts an :class:`~app.models.IngestRequest`
wrapping a :class:`~app.models.UniversalEnvelope`.

Two modes are supported via the ``direct`` flag:

* ``direct=false`` (default) — the envelope is serialised to JSON and
  forwarded to the configured webhook receiver so it flows through the
  full Pub/Sub → processor → agent pipeline.
* ``direct=true`` — the envelope is stored directly as a ``DataMetadata``
  item without touching the webhook pipeline (useful for batch imports or
  testing).
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app import config
from app.models import (
    CreateDataResponse,
    DataOwner,
    DataSource,
    ChannelRef,
    IngestRequest,
    MemoryCreate,
    MemoryType,
    UniversalEnvelope,
)
from app.storage import get_storage

logger = logging.getLogger("mem_dog.routers.ingest")

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingest"])

_WEBHOOK_TIMEOUT = 30.0


def _envelope_to_owner(env: UniversalEnvelope) -> Optional[DataOwner]:
    """Convert envelope origin → DataOwner for direct storage."""
    if not env.origin:
        return None
    channel_ref: Optional[ChannelRef] = None
    if env.origin.channel_type:
        channel_ref = ChannelRef(channel_type=env.origin.channel_type)
    source = DataSource(channel=channel_ref) if channel_ref else None
    return DataOwner(
        user={"user_id": env.origin.user_id} if env.origin.user_id else None,
        source=source,
    )


def _envelope_content(env: UniversalEnvelope) -> tuple[bytes, str]:
    """Extract ``(bytes, content_type)`` from an envelope's payload."""
    if env.content_json is not None:
        return json.dumps(env.content_json).encode("utf-8"), "application/json"
    if env.content_text is not None:
        mime = env.payload.mime_type or "text/plain"
        return env.content_text.encode("utf-8"), mime
    if env.content_b64 is not None:
        import base64
        data = base64.b64decode(env.content_b64)
        mime = env.payload.mime_type or "application/octet-stream"
        return data, mime
    # Fallback: store envelope itself as JSON
    return json.dumps(env.model_dump(mode="json")).encode("utf-8"), "application/json"


@router.post("", response_model=CreateDataResponse)
async def ingest(
    body: IngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Ingest data via the Universal Data Envelope.

    - ``direct=false``: forwards envelope to the webhook receiver (full pipeline).
    - ``direct=true``: stores directly in the API without pipeline processing.
    """
    env = body.envelope

    # Assign envelope ID if not provided
    if not env.envelope_id:
        env.envelope_id = uuid.uuid4().hex

    # Resolve authenticated user — prefer request.state (JWT/API key) over envelope
    auth_user_id = getattr(request.state, "user_id", None) or ""

    # Do not send to receiver when direct=true (store only, no pipeline)
    if body.direct:
        return await _store_direct(env, auth_user_id=auth_user_id)
    return await _forward_to_webhook(env, auth_user_id=auth_user_id)


async def _store_direct(env: UniversalEnvelope, auth_user_id: str = "") -> CreateDataResponse:
    """Store envelope directly without pipeline processing."""
    storage = get_storage()

    raw_bytes, content_type = _envelope_content(env)
    owner = _envelope_to_owner(env)

    memory_ids = list(env.context.memory_ids) if env.context.memory_ids else None
    tags = list(env.context.tags) if env.context.tags else []
    if env.origin.source_type:
        tags.append(f"source_type:{env.origin.source_type.value}")

    try:
        # Prefer authenticated user over envelope origin
        user_id = auth_user_id or config.DEFAULT_USER_ID
        if not auth_user_id and owner and owner.user and owner.user.get("user_id"):
            user_id = owner.user["user_id"]

        data_id, version = storage.create_data(
            content=raw_bytes,
            content_type=content_type,
            user=user_id,
            memory_ids=memory_ids,
            exclusive_memory_ids=bool(memory_ids),
            tags=tags or None,
            name=f"envelope-{env.envelope_id}",
            description=f"Universal envelope ({env.origin.source_type})",
            purpose="user_data",
            url=env.payload.url,
            mime_type=env.payload.mime_type,
            is_downloaded=env.payload.is_downloaded,
            owner=owner,
        )
        # Feed text content to Graphiti knowledge graph (non-blocking)
        if content_type.startswith("text/") or content_type == "application/json":
            asyncio.create_task(_ingest_to_graphiti(data_id, user_id, raw_bytes.decode("utf-8", errors="replace"), content_type))

        return CreateDataResponse(
            data_id=data_id,
            version=version,
            message="Envelope stored directly",
        )
    except Exception as exc:
        logger.exception("Failed to store envelope directly")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _forward_to_webhook(env: UniversalEnvelope, auth_user_id: str = "") -> CreateDataResponse:
    """Forward the envelope to the webhook receiver pipeline as { data, meta_data }.

    Acts as a trace origin: creates a per-ingest ``tracing`` memory and sets
    ``trace_memory_id`` in the meta_data payload so downstream services inherit it.
    When ``env.context.data_id`` and/or ``env.payload.is_downloaded`` are set, they
    are included in telemetry (mem-dog format) so the pipeline processes only once.
    """
    if not config.WEBHOOK_GATEWAY_URL or not config.WEBHOOK_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Webhook pipeline not configured (WEBHOOK_GATEWAY_URL / WEBHOOK_API_KEY missing).",
        )

    # Prefer authenticated user over envelope origin
    user_id = auth_user_id or (env.origin.user_id or "").strip() or config.DEFAULT_USER_ID

    # Resolve org_id and project_id from envelope context if available
    org_id = getattr(env.context, "org_id", None) or None
    project_id = getattr(env.context, "project_id", None) or None

    trace_memory_id: str | None = None
    if config.is_memories_enabled():
        try:
            storage = get_storage()
            mem_create = MemoryCreate(
                memory_type=MemoryType.TRACING,
                name=f"Ingest trace — {env.envelope_id or 'envelope'}",
                description="Per-ingest trace container for OTel spans",
                user_id=user_id,
                metadata={"source": "ingest", "envelope_id": env.envelope_id, "auto_created": True},
            )
            # Attach org/project if available
            if org_id:
                mem_create.org_id = org_id
            if project_id:
                mem_create.project_id = project_id
            mem = storage.create_memory(mem_create)
            trace_memory_id = mem.memory_id
        except Exception as exc:
            logger.warning("Could not create trace memory for ingest: %s", exc)

    # Build nested meta_data
    identity_block: dict = {"user_id": user_id}
    content_block: dict = {
        "source_type": env.origin.source_type.value if env.origin.source_type else "other",
    }
    if env.payload.mime_type:
        content_block["mime_type"] = env.payload.mime_type
    access_block: dict = {"is_downloaded": bool(env.payload.is_downloaded)}
    if env.context.data_id:
        access_block["data_id"] = env.context.data_id
    tracing_block: dict = {}
    if trace_memory_id:
        tracing_block["trace_memory_id"] = trace_memory_id

    nested_meta: dict = {
        "identity": identity_block,
        "content": content_block,
        "access": access_block,
    }
    if tracing_block:
        nested_meta["tracing"] = tracing_block
    if env.context.trace_id:
        nested_meta["__trace_context__"] = {"trace_id": env.context.trace_id}

    payload = {
        "data": env.model_dump(mode="json"),
        "meta_data": nested_meta,
    }

    try:
        async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
            resp = await client.post(
                config.WEBHOOK_GATEWAY_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {config.WEBHOOK_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Webhook returned HTTP {exc.response.status_code}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to forward to webhook: {exc}",
        ) from exc

    return CreateDataResponse(
        data_id=env.envelope_id,
        version=1,
        message="Envelope forwarded to webhook pipeline",
    )


async def _ingest_to_graphiti(data_id: str, user_id: str, text_content: str, mime_type: str):
    """Feed text content to Graphiti knowledge graph as an episode (non-blocking)."""
    try:
        from app.graphiti_client import is_graphiti_enabled, get_graphiti
        if not is_graphiti_enabled():
            return

        graphiti = await get_graphiti()
        if graphiti is None:
            return

        # Truncate very large texts for Graphiti (LLM context limits)
        body = text_content[:10000] if len(text_content) > 10000 else text_content

        from graphiti_core.nodes import EpisodeType
        await graphiti.add_episode(
            name=data_id,
            episode_body=body,
            source=EpisodeType.text,
            source_description=f"ingest:{mime_type} (user:{user_id})",
            reference_time=datetime.now(timezone.utc),
        )
        logger.info("Graphiti episode created from ingest data_id=%s", data_id)
    except Exception as exc:
        logger.warning("Graphiti ingest failed for data_id=%s: %s", data_id, exc)
