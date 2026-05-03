"""Publish inbound channel messages as memory records in the memdog API.

Every message processed by the gateway is stored as a data item linked to
a per-channel conversation memory.  This happens regardless of whether an
LLM provider is configured — AI enrichment is optional, but the raw
message always gets persisted.

Memory hierarchy:
  - ``openclaw-{channel_type}`` — per-channel conversation memory
  - ``timeline-{user_id}`` — auto-associated by the API
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from . import config
from . import supabase_reader

from .channels.base import NormalizedMessage

_log = logging.getLogger("webhook_gateway.memory")

_TIMEOUT_S = 10
_ensured_memories: set[str] = set()


def _api_headers() -> dict[str, str]:
    """Return auth headers for memdog API calls."""
    h: dict[str, str] = {}
    if config.MEM_DOG_API_KEY:
        h["x-api-key"] = config.MEM_DOG_API_KEY
    return h


def _memory_id_for_channel(channel_type: str) -> str:
    return f"openclaw-{channel_type}"


def _memory_exists_in_supabase(memory_id: str) -> bool | None:
    """Check if a memory exists via direct Supabase read.

    Returns True/False on success, None to signal fallback to API.
    Memory blob path: ``{user_id}/custom/{memory_id}/meta.json``
    (openclaw-* IDs are inferred as ``custom`` type by the API).
    """
    if not supabase_reader.is_available():
        return None
    path = f"{config.DEFAULT_USER_ID}/custom/{memory_id}/meta.json"
    return supabase_reader.blob_exists("memories", path)


def _ensure_channel_memory(channel_type: str) -> str | None:
    """Create the channel conversation memory if it doesn't exist yet."""
    if not config.MEM_DOG_API_URL:
        return None

    mid = _memory_id_for_channel(channel_type)
    if mid in _ensured_memories:
        return mid

    base = f"{config.MEM_DOG_API_URL}/api/v1/memories"

    # Fast path: direct Supabase check
    supa_exists = _memory_exists_in_supabase(mid)
    if supa_exists is True:
        _ensured_memories.add(mid)
        return mid

    # Fallback: API check (also handles supa_exists is None)
    headers = _api_headers()
    if supa_exists is None:
        try:
            resp = httpx.get(f"{base}/{mid}", headers=headers, timeout=_TIMEOUT_S)
            if resp.status_code == 200:
                _ensured_memories.add(mid)
                return mid
        except Exception:
            pass

    try:
        resp = httpx.post(
            base,
            json={
                "memory_id": mid,
                "memory_type": "conversation",
                "name": f"OpenClaw — {channel_type}",
                "description": (
                    f"Messages received through the {channel_type} channel "
                    f"via the Webhook Gateway."
                ),
                "user_id": config.DEFAULT_USER_ID,
                "metadata": {
                    "source": "webhook_gateway",
                    "channel_type": channel_type,
                    "auto_created": True,
                },
            },
            headers=headers,
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        _ensured_memories.add(mid)
        _log.info("Created channel memory: %s", mid)
        return mid
    except Exception as exc:
        _log.warning("Could not ensure channel memory %s: %s", mid, exc)
        return mid  # still return the id — the API will accept the data item


async def publish_to_memory(
    msg: NormalizedMessage,
    *,
    resolved_user_id: str | None = None,
    trace_id: str | None = None,
    llm_classification: dict[str, Any] | None = None,
) -> str | None:
    """Store the message as a data item in the memdog API.

    Returns the ``data_id`` on success, ``None`` on failure.
    """
    if not config.MEM_DOG_API_URL:
        _log.debug("MEM_DOG_API_URL not set — skipping memory publish")
        return None

    channel_memory_id = _ensure_channel_memory(msg.channel_type)
    user_id = resolved_user_id or msg.user_id or config.DEFAULT_USER_ID

    memory_ids = []
    if channel_memory_id:
        memory_ids.append(channel_memory_id)

    content: dict[str, Any] = {}
    if msg.text:
        content["text"] = msg.text
    if msg.subject:
        content["subject"] = msg.subject
    if msg.attachments:
        content["attachments"] = msg.attachments
    if msg.recording_url:
        content["recording_url"] = msg.recording_url
    if msg.participants:
        content["participants"] = msg.participants

    content["channel"] = {
        "type": msg.channel_type,
        "channel_id": msg.channel_id,
        "peer_id": msg.peer_id,
        "thread_id": msg.thread_id,
        "message_id": msg.message_id,
    }

    if llm_classification:
        content["llm_classification"] = llm_classification

    tags = [
        f"channel:{msg.channel_type}",
        "source:webhook_gateway",
    ]
    if msg.peer_id:
        tags.append(f"peer:{msg.peer_id}")
    if trace_id:
        tags.append(f"trace_id:{trace_id}")
    if llm_classification:
        msg_type = llm_classification.get("type", "")
        if msg_type:
            tags.append(f"msg_type:{msg_type}")

    name = msg.subject or (msg.text[:80] if msg.text else f"{msg.channel_type} message")
    now = datetime.now(timezone.utc).isoformat()

    post_data: dict[str, str] = {
        "content": json.dumps(content, default=str),
        "name": name,
        "description": f"[{msg.channel_type}] message via Webhook Gateway at {now}",
        "tags": ",".join(tags),
        "owner_user_id": user_id,
    }
    if memory_ids:
        post_data["memory_ids"] = ",".join(memory_ids)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, headers=_api_headers()) as client:
            resp = await client.post(
                f"{config.MEM_DOG_API_URL}/api/v1/data",
                data=post_data,
            )
            resp.raise_for_status()
            body = resp.json()
            data_id = body.get("data_id") or body.get("id")
            _log.info(
                "Published %s message to memory (data_id=%s, memory=%s)",
                msg.channel_type, data_id, channel_memory_id,
            )
            return data_id
    except Exception as exc:
        _log.warning("Failed to publish to memory: %s", exc)
        return None
