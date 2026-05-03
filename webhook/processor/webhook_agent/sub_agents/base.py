"""Base class for all typed sub-agents.

Every sub-agent inherits from ``BaseSubAgent`` and only needs to declare
three class variables (``AGENT_TYPE``, ``AGENT_PURPOSE``, ``MIME_PATTERNS``)
plus a ``process()`` stub.  All HTTP work is delegated to the ``api_client``
singletons — no raw HTTP calls appear in sub-agent files.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ..api_client import data_client, stats_client, tracking_client
from ..meta_schema import (
    get_data_id, get_is_downloaded, get_memory, get_mime_type, get_owner,
    get_session_id, get_trace_memory_id, get_url, get_user_id, get_version,
)

if TYPE_CHECKING:
    from ..group_context import GroupContext

logger = logging.getLogger("mem_dog.webhook.sub_agents.base")


class BaseSubAgent(ABC):
    """Abstract base for all data-type sub-agents.

    Class variables to define in each subclass::

        AGENT_TYPE    = "pdf"
        AGENT_PURPOSE = "Processes PDF documents"
        MIME_PATTERNS = ["application/pdf", "application/x-pdf"]

    Each concrete subclass is instantiated **once** at module load time
    (module-level singleton pattern) so instance IDs are stable across
    requests within a single process lifetime.
    """

    AGENT_TYPE: str = ""
    AGENT_PURPOSE: str = ""
    MIME_PATTERNS: list[str] = []
    #: Model tier used for LLM inference.  Override in subclasses.
    #: ``"small"``  → Gemma 3 1B  (simple structured/IoT data)
    #: ``"medium"`` → Gemma 3 4B  (docs, code, comms — default)
    #: ``"large"``  → Gemma 3 12B (PDFs, office docs, web pages, spatial)
    MODEL_TIER: str = "medium"

    def __init__(self) -> None:
        self.instance_id: str = f"{self.AGENT_TYPE}-{uuid.uuid4().hex[:12]}"
        self.timeline_memory_id: str = f"timeline-{self.instance_id}"
        self.session_memory_id: str = f"session-{self.instance_id}"
        logger.info(
            "Sub-agent initialised",
            extra={
                "agent_type": self.AGENT_TYPE,
                "instance_id": self.instance_id,
            },
        )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def publish(self) -> dict[str, Any]:
        """Return the agent's identity manifest.

        Called by the router to embed agent metadata in the routing
        response so callers always know which agent handled a payload
        and what its purpose is.

        Returns:
            Dict with ``agent_type``, ``agent_purpose``, ``instance_id``,
            ``timeline_memory_id``, and ``session_memory_id``.
        """
        return {
            "agent_type": self.AGENT_TYPE,
            "agent_purpose": self.AGENT_PURPOSE,
            "instance_id": self.instance_id,
            "timeline_memory_id": self.timeline_memory_id,
            "session_memory_id": self.session_memory_id,
        }

    # ------------------------------------------------------------------
    # Write / Delete
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten_memory_dict(memory: dict) -> list[str]:
        """Flatten ``{ <type>: [<ids>] }`` back to a deduplicated ID list."""
        seen: set[str] = set()
        flat: list[str] = []
        for ids in memory.values():
            if isinstance(ids, list):
                for mid in ids:
                    if mid not in seen:
                        seen.add(mid)
                        flat.append(mid)
        return flat

    def write_record(
        self,
        payload_json: str,
        name: str = "event",
        group_context: "GroupContext | None" = None,
        extra_tags: "list[str] | None" = None,
        trace_context: "dict | None" = None,
        meta_data: "dict | None" = None,
    ) -> dict[str, Any]:
        """Store a payload and return a memory-of-record dict.

        Attaches the data only to pre-existing memories; the agent does not
        create memories. Memory IDs come from:

        * **memory** dict in *meta_data* — ``{ <type>: [<ids>] }``
          (canonical format used by all pipeline stages).
        * Legacy **memory_list** — flat list, used as fallback.
        * **Group context** — timeline and session IDs from the router when
          neither ``memory`` nor ``memory_list`` is provided.

        Webhook agents do not maintain their own memory; created events are
        not attached to the agent's own timeline or session.

        Args:
            payload_json: The raw payload as a JSON string.
            name: Human-readable name for the data entry.
            group_context: Optional group context produced by the router.
            extra_tags: Additional tags appended after the standard set.
            trace_context: Optional dict with ``trace_id`` and
                ``parent_span_id`` propagated from the router so this
                sub-agent's span is linked into the same OTel trace.
            meta_data: Optional telemetry dict carrying ``memory``
                (preferred, type-keyed) or legacy ``memory_list``,
                ``trace_memory_id``, ``session_id``, provenance fields,
                etc.  The agent's own timeline/session are never attached.

        Returns:
            A memory-of-record dict containing ``data_id``, ``version``,
            memory IDs, agent identity, and optionally ``group_context``.
        """
        meta_data = meta_data or {}

        memory_dict: dict = get_memory(meta_data) or {}
        memory_from_dict = self._flatten_memory_dict(memory_dict) if memory_dict else []
        memory_list: list[str] = memory_from_dict or meta_data.get("memory_list") or []

        url: str | None = get_url(meta_data) or None
        mime_type: str | None = get_mime_type(meta_data) or None
        is_downloaded: bool = get_is_downloaded(meta_data)
        owner: dict | None = get_owner(meta_data) or None

        conversation_memory_id: str | None = (
            group_context.conversation_memory_id if group_context else None
        )

        memory_ids: list[str] = []
        tags: list[str] = [f"agent_type:{self.AGENT_TYPE}", self.instance_id]

        creator_user_id: str | None = None
        if group_context is not None:
            creator_user_id = group_context.user_id
        if not creator_user_id:
            creator_user_id = get_user_id(meta_data) or (
                (owner or {}).get("user") or {}
            ).get("user_id")
        if creator_user_id:
            tags.append(f"user_id:{creator_user_id}")

        if memory_list:
            memory_ids = list(memory_list)
        elif group_context is not None:
            memory_ids = [
                group_context.timeline_memory_id,
                group_context.session_memory_id,
            ]
            if conversation_memory_id:
                memory_ids.append(conversation_memory_id)
            if creator_user_id:
                personal_timeline_id = f"timeline-{creator_user_id}"
                if personal_timeline_id not in memory_ids:
                    memory_ids.append(personal_timeline_id)
            tags += [
                f"group_id:{group_context.group_id}",
            ]
            if group_context.channel_type:
                tags.append(f"channel_type:{group_context.channel_type}")

        trace_memory_id = get_trace_memory_id(meta_data)
        if trace_memory_id and trace_memory_id not in memory_ids:
            memory_ids.append(trace_memory_id)
        session_id = get_session_id(meta_data)
        if session_id:
            session_memory_id = f"session-{session_id}"
            if session_memory_id not in memory_ids:
                memory_ids.append(session_memory_id)

        # Webhook agents do not attach to their own memory
        for own_id in (self.timeline_memory_id, self.session_memory_id):
            if own_id in memory_ids:
                memory_ids.remove(own_id)

        if extra_tags:
            tags += extra_tags

        span_start = datetime.now(timezone.utc)

        try:
            result = data_client.create(
                content=payload_json,
                name=name,
                description=(
                    f"Ingested by {self.instance_id} "
                    f"(group: {group_context.group_id if group_context else 'none'})"
                ),
                tags=tags,
                memory_ids=memory_ids,
                exclusive=True,
                url=url,
                mime_type=mime_type,
                is_downloaded=is_downloaded,
                owner=owner,
                owner_user_id=creator_user_id,
            )
        except Exception as exc:
            logger.error("Failed to create data entry: %s", exc)
            if trace_context:
                tracking_client.write_span(
                    trace_id=trace_context.get("trace_id", ""),
                    span_id=uuid.uuid4().hex[:16],
                    name=f"webhook.subagent.{self.AGENT_TYPE}",
                    stage="subagent",
                    service_name=f"subagent-{self.AGENT_TYPE}",
                    service_type="gcp_cloud_run_adk",
                    status_code="ERROR",
                    kind="INTERNAL",
                    start_time=span_start,
                    end_time=datetime.now(timezone.utc),
                    parent_span_id=trace_context.get("parent_span_id"),
                    trace_memory_id=get_trace_memory_id(meta_data),
                    user_id=creator_user_id,
                    data_id=get_data_id(meta_data),
                    version=get_version(meta_data),
                    mime_type=mime_type or None,
                    attributes={
                        "agent_type": self.AGENT_TYPE,
                        "error": str(exc),
                    },
                )
            return {
                "status": "error",
                "instance_id": self.instance_id,
                "error_message": str(exc),
            }

        span_end = datetime.now(timezone.utc)
        stats_client.increment(self.AGENT_TYPE)

        if trace_context:
            tracking_client.write_span(
                trace_id=trace_context.get("trace_id", ""),
                span_id=uuid.uuid4().hex[:16],
                name=f"webhook.subagent.{self.AGENT_TYPE}",
                stage="subagent",
                service_name=f"subagent-{self.AGENT_TYPE}",
                service_type="gcp_cloud_run_adk",
                status_code="OK",
                kind="INTERNAL",
                start_time=span_start,
                end_time=span_end,
                parent_span_id=trace_context.get("parent_span_id"),
                trace_memory_id=get_trace_memory_id(meta_data),
                user_id=group_context.user_id if group_context else creator_user_id,
                data_id=result.get("data_id"),
                version=result.get("version"),
                mime_type=mime_type or None,
                attributes={
                    "agent_type": self.AGENT_TYPE,
                    "agent_purpose": self.AGENT_PURPOSE,
                    "instance_id": self.instance_id,
                    "group_id": group_context.group_id if group_context else None,
                },
            )

        return {
            "status": "success",
            "data_id": result.get("data_id"),
            "version": result.get("version"),
            "memory_ids": memory_ids,
            "group_context": asdict(group_context) if group_context and hasattr(group_context, "__dataclass_fields__") else None,
            "agent": self.publish(),
        }

    def delete_record(self, data_id: str, user_id: str | None = None) -> dict[str, Any]:
        """Delete a data item and decrement the agent-type count.

        Looks up the ``agent_type:*`` tag on the data item so the correct
        type count is decremented even when called from a generic context.

        Args:
            data_id: The data item to delete.
            user_id: Owner user ID (for multitenancy path resolution).

        Returns:
            A dict with ``status``, ``data_id``, and the decremented type.
        """
        agent_type_to_decrement = self.AGENT_TYPE
        try:
            meta = data_client.get_metadata(data_id, user_id=user_id)
            tags: list[str] = meta.get("tags", [])
            for tag in tags:
                if tag.startswith("agent_type:"):
                    agent_type_to_decrement = tag.split(":", 1)[1]
                    break
        except Exception as exc:
            logger.warning("Could not read metadata for %s: %s — using own type", data_id, exc)

        stats_client.decrement(agent_type_to_decrement)

        # Try to find the owner user_id from metadata tags for correct multitenancy path
        owner_user_id: str | None = None
        for tag in tags:
            if tag.startswith("user_id:"):
                owner_user_id = tag.split(":", 1)[1]
                break

        try:
            data_client.delete(data_id, user_id=owner_user_id)
        except Exception as exc:
            logger.error("Failed to delete data %s: %s", data_id, exc)
            return {
                "status": "error",
                "data_id": data_id,
                "error_message": str(exc),
            }

        return {
            "status": "success",
            "data_id": data_id,
            "decremented_type": agent_type_to_decrement,
        }

    # ------------------------------------------------------------------
    # Processing (subclass responsibility)
    # ------------------------------------------------------------------

    def process(
        self,
        payload_json: str,
        data_id: str,
        group_context: "GroupContext | None" = None,
        payload_meta: "dict | None" = None,
        trace_context: "dict | None" = None,
    ) -> dict[str, Any]:
        """Log-wrapped entry point called by the router.

        Logs the incoming arguments, delegates to :meth:`_process`, and
        logs the result before returning it.

        Args:
            payload_json: The raw payload as a JSON string.
            data_id: The memdog data ID returned by ``write_record()``.
            group_context: Optional group context forwarded from the router.
            payload_meta: Optional dict carrying detection-layer metadata.
            trace_context: Optional OTel trace context dict (``trace_id``,
                ``parent_span_id``) forwarded from the router.  Not currently
                used to emit additional spans, but available for future use.

        Returns:
            Whatever :meth:`_process` returns.
        """
        logger.info(
            "[%s] process() CALLED | instance=%s  data_id=%s  payload_chars=%d  payload_meta=%s  group=%s",
            self.AGENT_TYPE,
            self.instance_id,
            data_id,
            len(payload_json) if payload_json else 0,
            payload_meta,
            (group_context.group_id if group_context else None),
        )
        logger.debug("[%s] process() payload_json (first 500 chars) |\n%s", self.AGENT_TYPE, (payload_json or "")[:500])

        result = self._process(payload_json, data_id, group_context, payload_meta)

        logger.info(
            "[%s] process() RETURNED | data_id=%s  status=%s",
            self.AGENT_TYPE,
            data_id,
            result.get("status") if isinstance(result, dict) else type(result).__name__,
        )
        logger.debug("[%s] process() full result | %s", self.AGENT_TYPE, result)

        return result

    @abstractmethod
    def _process(
        self,
        payload_json: str,
        data_id: str,
        group_context: "GroupContext | None" = None,
        payload_meta: "dict | None" = None,
    ) -> dict[str, Any]:
        """Stage, analyse, and enrich a payload for one data record.

        Tier-1 (text) sub-agents delegate to
        :func:`~sub_agents.llm_utils.analyse_payload`, which:

        1. Downloads the payload's content and persists it to the GCS
           staging bucket (``WEBHOOK_STAGING_BUCKET``) as ``raw`` +
           ``meta.json`` under ``{agent_type}/{data_id}/``.
        2. Truncates the content to 4 000 chars and runs Gemma 3 1B via
           LiteLLM (configured by ``SUB_AGENT_MODEL`` /
           ``SUB_AGENT_API_BASE``).
        3. Stores the analysis as a viewpoint linked to *data_id*.
        4. Triggers vector embedding generation for *data_id*.

        Tier-2+ sub-agents (vision, audio, spatial) will use their own
        pipelines once implemented.

        Args:
            payload_json: The raw payload as a JSON string.
            data_id: The memdog data ID returned by ``write_record()``.
                All enrichment objects (viewpoint, embedding) are linked
                to this ID.
            group_context: Optional group context forwarded from the
                router.  Written into ``meta.json`` for full provenance.
            payload_meta: Optional dict carrying detection-layer metadata
                (``detection_layer``, ``mime_type``) forwarded from the
                router.

        Returns:
            A processing result dict containing at minimum ``status``,
            ``agent_type``, and ``data_id``.  On success, also contains
            ``staged_uri``, ``content_length``, ``content_source``,
            ``analysis``, ``viewpoint``, ``embedding``, and ``metadata``.
            On failure, contains ``error`` instead of analysis fields.
        """
