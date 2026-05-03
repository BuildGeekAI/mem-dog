"""API-layer webhook pipeline tracking.

Writes a ``stored`` event to the ``timeline-webhook-tracking`` memory (owned
by the default user) whenever a webhook agent data item is successfully written
to storage.  This represents the ``api`` stage in the full pipeline:

    api → receiver → pubsub → processor → agent

The hook fires when ``POST /api/v1/data`` is called with an ``agent_type:*``
tag (set by every webhook sub-agent in ``sub_agents/base.py``) and without
the ``source:webhook_pipeline`` tag (which marks the tracking events
themselves and must not trigger a second write — no recursion).

All writes are best-effort — exceptions are swallowed so tracking never
breaks the main data-creation path.

Usage (from data.py)::

    from app import tracking
    from fastapi import BackgroundTasks

    @router.post("")
    async def create_data(..., background_tasks: BackgroundTasks):
        data_id, version = storage.create_data(...)
        if tracking.should_track(parsed_tags):
            background_tasks.add_task(
                tracking.write_api_event,
                storage=storage,
                data_id=data_id,
                name=data_name,
                tags=parsed_tags or [],
                memory_ids=parsed_memory_ids or [],
            )
"""

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from app import config
from app.models import DataDeviceInfo, MemoryCreate, MemoryType

if TYPE_CHECKING:
    from app.storage import Storage

logger = logging.getLogger("mem_dog.api.tracking")

TRACKING_TIMELINE_ID = "timeline-webhook-tracking"
TRACKING_USER_ID = config.DEFAULT_USER_ID
_PIPELINE_LABEL = "api → receiver → pubsub → processor → agent"

# Module-level flag so the memory-existence check runs only once per process.
_timeline_ensured: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_tracking_timeline(storage: "Storage") -> None:
    """Idempotently create the ``timeline-webhook-tracking`` memory.

    Uses a module-level flag so the ``get_memory`` call is only made once
    per process lifetime.  Best-effort — never raises.

    Args:
        storage: The Storage instance to write through.
    """
    global _timeline_ensured
    if _timeline_ensured:
        return

    try:
        if not config.is_memories_enabled():
            return

        if storage.get_memory(TRACKING_TIMELINE_ID) is not None:
            _timeline_ensured = True
            return

        storage.create_memory(
            MemoryCreate(
                memory_type=MemoryType.TIMELINE,
                name="Webhook Tracking Timeline",
                description=(
                    "Tracks every webhook request through the full pipeline: "
                    "receiver → Pub/Sub → processor → agent.  "
                    "Each entry is one pipeline-stage event carrying the service "
                    "name, status, and stage-specific details."
                ),
                user_id=TRACKING_USER_ID,
                metadata={
                    "source": "webhook_pipeline",
                    "pipeline": _PIPELINE_LABEL,
                    "auto_created": True,
                },
            ),
            memory_id_override=TRACKING_TIMELINE_ID,
        )
        _timeline_ensured = True
        logger.info(
            "Created webhook tracking timeline: %s (owner=%s)",
            TRACKING_TIMELINE_ID, TRACKING_USER_ID,
        )
    except Exception as exc:
        logger.warning("Could not ensure tracking timeline: %s", exc)


def _extract_agent_type(tags: List[str]) -> Optional[str]:
    """Return the value after the ``agent_type:`` prefix, or ``None``."""
    for tag in tags:
        if tag.startswith("agent_type:"):
            return tag.split(":", 1)[1]
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def should_track(tags: Optional[List[str]]) -> bool:
    """Return ``True`` when this data item should generate an API tracking event.

    The event fires when:

    * At least one ``agent_type:*`` tag is present — meaning a webhook
      sub-agent wrote the data item.
    * The ``source:webhook_pipeline`` tag is absent — meaning this is actual
      payload data, not a tracking event itself (prevents recursion).

    Args:
        tags: The tag list that will be stored with the data item.

    Returns:
        ``True`` if a tracking event should be written, ``False`` otherwise.
    """
    if not tags:
        return False
    has_agent_type = any(t.startswith("agent_type:") for t in tags)
    is_tracking_event = "source:webhook_pipeline" in tags
    return has_agent_type and not is_tracking_event


def write_api_event(
    storage: "Storage",
    data_id: str,
    name: Optional[str],
    tags: List[str],
    memory_ids: List[str],
) -> None:
    """Write an ``api | stored`` event to the webhook tracking timeline.

    Intended to run as a :class:`fastapi.BackgroundTasks` task so it does
    not block the HTTP response.  Best-effort — never raises.

    Args:
        storage: The Storage instance to write through.
        data_id: The newly created data item ID.
        name: The data item name (may be ``None``).
        tags: Tags stored on the data item (used to extract ``agent_type``).
        memory_ids: The memory IDs the data item was explicitly associated
            with (the caller-supplied list, not the auto-resolved list).
    """
    try:
        _ensure_tracking_timeline(storage)

        agent_type = _extract_agent_type(tags)
        event = {
            "stage": "api",
            "service": "memdog-api",
            "service_type": "gcp_cloud_run_fastapi",
            "status": "stored",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline": _PIPELINE_LABEL,
            "details": {
                "data_id": data_id,
                "name": name,
                "agent_type": agent_type,
                "memory_ids": memory_ids,
                "tags": tags,
            },
        }

        event_tags = [
            "stage:api",
            "service:memdog-api",
            "status:stored",
            "source:webhook_pipeline",
        ]
        if agent_type:
            event_tags.append(f"agent_type:{agent_type}")

        storage.create_data(
            content=json.dumps(event, default=str).encode("utf-8"),
            content_type="application/json",
            user=TRACKING_USER_ID,
            memory_ids=[TRACKING_TIMELINE_ID],
            tags=event_tags,
            name="memdog-api | stored",
            description=f"[memdog-api] STORED — api stage | data_id={data_id}",
            exclusive_memory_ids=True,
        )
        logger.info(
            "API tracking event written | data_id=%s  agent_type=%s",
            data_id, agent_type,
        )
    except Exception as exc:
        logger.warning(
            "Failed to write API tracking event for %s: %s", data_id, exc
        )
