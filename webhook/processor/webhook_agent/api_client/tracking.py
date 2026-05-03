"""Webhook pipeline telemetry client.

Writes OpenTelemetry-compatible spans to the inherited ``trace_memory_id``
so the full journey of every webhook — receiver → Pub/Sub → processor →
agent → sub-agent — is visible as a linked trace in the Telemetry UI tab.
The agent never creates tracing memories; it inherits them from upstream.

Span schema
-----------
Each span is stored as a JSON data item with the following fields:

    trace_id        128-bit hex (32 chars) — same for all spans in one webhook
    span_id         64-bit hex (16 chars)  — unique per stage
    parent_span_id  64-bit hex or null     — links to the calling stage
    name            operation name, e.g. "webhook.receiver"
    kind            SERVER | CLIENT | INTERNAL | PRODUCER | CONSUMER
    service_name    human-readable service name
    service_type    GCP service classification
    status          {code: OK|ERROR|UNSET, message: ""}
    start_time      ISO-8601 UTC
    end_time        ISO-8601 UTC or null
    duration_ms     wall-clock milliseconds or null
    attributes      stage-specific key-value metadata
    events          list of {name, timestamp, attributes} sub-events

Tags on each data item
----------------------
    trace_id:{trace_id}   — enables grouping all spans of one trace
    span_id:{span_id}
    stage:{stage}         — receiver | processor | agent | router | subagent
    service:{service}
    status:{OK|ERROR|UNSET}
    source:webhook_telemetry

All writes are best-effort — exceptions are swallowed so telemetry never
blocks or breaks the main processing path.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import AGENT_USER_ID, DEFAULT_TIMEOUT, MEM_DOG_API_URL
from .session import _session

logger = logging.getLogger("mem_dog.webhook.api_client.tracking")

_PIPELINE_LABEL = "api → receiver → pubsub → processor → agent"


# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------

def generate_trace_id() -> str:
    """Return a 128-bit trace ID as a 32-char lowercase hex string."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:0] or uuid.uuid4().hex


def generate_span_id() -> str:
    """Return a 64-bit span ID as a 16-char lowercase hex string."""
    return uuid.uuid4().hex[:16]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class WebhookTrackingClient:
    """Writes OTel-compatible pipeline spans to the inherited trace memory.

    Does not create memories.  Spans are only written when a
    ``trace_memory_id`` is provided by the upstream caller.

    Args:
        base_url: Base URL of the mem-dog API.  Defaults to
            :data:`~config.MEM_DOG_API_URL`.
    """

    def __init__(self, base_url: str = MEM_DOG_API_URL) -> None:
        self._data_base = f"{base_url}/api/v1/data"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_span(
        self,
        *,
        trace_id: str,
        span_id: str,
        name: str,
        stage: str,
        service_name: str,
        service_type: str,
        status_code: str = "OK",
        status_message: str = "",
        kind: str = "INTERNAL",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        events: list[dict[str, Any]] | None = None,
        trace_memory_id: str | None = None,
        purpose: str | None = None,
        # Canonical EventMeta tags — auto-merged into attributes and tag list
        user_id: str | None = None,
        data_id: str | None = None,
        version: int | None = None,
        mime_type: str | None = None,
    ) -> str | None:
        """Write an OTel-compatible span to a telemetry/trace memory.

        Best-effort — never raises.  Logs a warning on failure.

        When ``trace_memory_id`` is provided, the span is written to that
        per-invocation trace memory inherited from upstream.

        Args:
            trace_id: 32-char hex trace identifier (shared by all spans in
                one webhook invocation).
            span_id: 16-char hex span identifier (unique per stage).
            name: Operation name, e.g. ``"webhook.receiver"``.
            stage: Pipeline stage label used in tags
                (``"receiver"``, ``"processor"``, ``"agent"``,
                ``"router"``, ``"subagent"``).
            service_name: Human-readable service name.
            service_type: GCP service classification
                (e.g. ``"gcp_cloud_function_http"``).
            status_code: ``"OK"``, ``"ERROR"``, or ``"UNSET"``.
            status_message: Optional human-readable status detail.
            kind: OTel SpanKind — ``"SERVER"``, ``"CLIENT"``,
                ``"INTERNAL"``, ``"PRODUCER"``, or ``"CONSUMER"``.
            start_time: Span start (defaults to now if omitted).
            end_time: Span end (``None`` if still in progress).
            parent_span_id: 16-char hex ID of the parent span, or
                ``None`` for a root span.
            attributes: Stage-specific key-value metadata.
            events: List of ``{name, timestamp, attributes}`` dicts.
            trace_memory_id: Target trace memory ID inherited from upstream.
                If absent, the span write is skipped.
            purpose: Optional purpose for the written data (e.g. ``trace_stage``).
        """
        if not trace_memory_id:
            logger.debug("Skipping span write: no trace_memory_id provided")
            return None
        memory_id = trace_memory_id

        now = datetime.now(timezone.utc)
        t_start = start_time or now
        t_end = end_time

        duration_ms: float | None = None
        if t_start and t_end:
            duration_ms = (t_end - t_start).total_seconds() * 1000

        span: dict[str, Any] = {
            "trace_id": trace_id,
            "span_id": span_id,
            "name": name,
            "kind": kind,
            "service_name": service_name,
            "service_type": service_type,
            "status": {"code": status_code, "message": status_message},
            "start_time": t_start.isoformat(),
            "end_time": t_end.isoformat() if t_end else None,
            "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
            "pipeline": _PIPELINE_LABEL,
        }
        if parent_span_id:
            span["parent_span_id"] = parent_span_id

        # Merge canonical EventMeta fields into attributes (caller values take precedence)
        enriched: dict[str, Any] = dict(attributes or {})
        if user_id:
            enriched.setdefault("user_id", user_id)
        if data_id:
            enriched.setdefault("data_id", data_id)
        if version is not None:
            enriched.setdefault("version", version)
        if mime_type:
            enriched.setdefault("mime_type", mime_type)
        if enriched:
            span["attributes"] = enriched

        if events:
            span["events"] = events

        tags = [
            f"trace_id:{trace_id}",
            f"span_id:{span_id}",
            f"stage:{stage}",
            f"service:{service_name}",
            f"status:{status_code}",
            f"kind:{kind}",
            "source:webhook_telemetry",
        ]
        if parent_span_id:
            tags.append(f"parent_span_id:{parent_span_id}")
        # Canonical EventMeta tags for filtering/search
        if user_id:
            tags.append(f"user_id:{user_id}")
        if data_id:
            tags.append(f"data_id:{data_id}")
        if version is not None:
            tags.append(f"version:{version}")
        if mime_type:
            tags.append(f"mime_type:{mime_type}")

        post_data = {
            "content": json.dumps(span, default=str),
            "name": f"{name} | {status_code}",
            "description": (
                f"[{service_name}] {name} — {kind} span — {status_code}"
            ),
            "tags": ",".join(tags),
            "memory_ids": memory_id,
            "exclusive": "true",
            "owner_user_id": user_id or AGENT_USER_ID,
        }
        if purpose:
            post_data["purpose"] = purpose
        try:
            resp = _session.post(
                self._data_base,
                data=post_data,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            written_data_id: str | None = resp.json().get("data_id")
            logger.info(
                "Telemetry span written | trace=%s span=%s name=%s status=%s data_id=%s",
                trace_id[:8], span_id[:8], name, status_code, written_data_id,
            )
            return written_data_id
        except Exception as exc:
            logger.warning(
                "Failed to write telemetry span (name=%s status=%s): %s",
                name, status_code, exc,
            )
            return None
