"""Payload router.

Implements the multi-layer metadata-based detection pipeline and dispatches
each payload to the correct sub-agent, passing the resolved group
context so related payloads share memories.

Message format
--------------
Payloads are normalized to ``{ "data": {...}, "meta_data": {...} }``.
Known meta keys (data_id, memory, trace_memory_id, __trace_context__,
user_id, mimetype, url, is_downloaded, etc.) live in meta_data; the rest is in
data.  If the payload is not in that shape, :func:`normalize_message` splits
it (accepts legacy ``telemetry`` as an alias for ``meta_data``).  All
metadata is preserved downstream; nothing is deleted when passing to
sub-agents or re-invokes.

Detection layers
----------------
0b. **URL not downloaded** — when ``url`` is in meta but ``data_id``/``is_downloaded``
    are not set, route to the download subagent first.
1. **Explicit field** — ``data_type`` or ``source_type`` in the payload.
2. **Payload field heuristic** — inspects key names and value patterns.
3. **MIME registry** — best-match on agent ``MIME_PATTERNS``.
4. **URL extension sniff** — ``url`` field suffix (``.mp4``, ``.pdf``, etc.).
5. **Fallback** — :class:`~sub_agents.binary.binary_blob.BinaryBlobAgent`.

After a record is written (``write_record()``), the router immediately
calls ``agent.process()`` to kick off the staged-download + enrich
pipeline for Tier-1 agents (GCS staging → Gemma analysis → viewpoint →
embedding).  The process result is embedded in the routing response under
the ``process`` key so the ADK orchestrator can report it to the caller.

Telemetry
---------
The processor injects ``{"__trace_context__": {...}}`` into the payload dict
before calling the ADK agent.  ``route_payload()`` pops this key before
running detection (so it never leaks into the stored data record) and uses
the extracted ``trace_id`` + ``parent_span_id`` to write two OTel spans:

* ``webhook.agent``  — SERVER span covering the full route_payload() call.
* ``webhook.agent.router`` — INTERNAL span covering detection + sub-agent
  dispatch (child of the agent span).

Both spans are written via the shared :data:`tracking_client` which stores
them in the inherited ``trace_memory_id`` from upstream.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .api_client import memory_client, tracking_client
from .api_client.ai import AIClient as _AIClient
from .group_context import build_group_context, ensure_group_memories
from .meta_schema import (
    normalize_meta_data,
    get_user_id, get_data_id, get_mime_type, get_url, get_download_url,
    get_gcs_uri, get_is_downloaded, get_owner, get_trace_memory_id,
    get_memory, get_session_id, get_version, get_version_label,
    get_prompt, get_crawl, get_channel_message, get_source_type,
    set_field, _KNOWN_FLAT_KEYS,
)
from .sub_agents import AGENT_REGISTRY, MIME_REGISTRY

logger = logging.getLogger("mem_dog.webhook.router")

_AGENT_SERVICE = "webhook-agent"
_AGENT_SERVICE_TYPE = "gcp_cloud_run_adk"

# ---------------------------------------------------------------------------
# Per-agent-type AI processing gate
# ---------------------------------------------------------------------------

# Previously disabled json, chat, channel_message, binary_blob — now enabled
# since small-tier types route to self-hosted Phi-3 Mini at zero API cost.
_PROCESSING_DISABLED_BY_DEFAULT: frozenset[str] = frozenset()
_ai_client_for_prefs = _AIClient()


def _is_processing_enabled(agent_type: str, user_id: str | None) -> bool:
    """Return whether AI processing (viewpoint + embedding) should run.

    Checks the user's ``agent_processing_flags`` preference first; falls
    back to hardcoded defaults (all types enabled).
    """
    if user_id:
        prefs = _ai_client_for_prefs.get_user_preferences(user_id)
        flags = prefs.get("agent_processing_flags") or {}
        if agent_type in flags:
            return bool(flags[agent_type])
    return agent_type not in _PROCESSING_DISABLED_BY_DEFAULT

# ---------------------------------------------------------------------------
# URL extension → agent_type mapping (Layer 4)
# ---------------------------------------------------------------------------

_EXT_MAP: dict[str, str] = {
    # Video
    ".mp4": "video_url", ".mov": "video_url", ".avi": "video_url",
    ".mkv": "video_url", ".webm": "video_url",
    # Audio
    ".mp3": "audio_url", ".wav": "audio_url", ".flac": "audio_url",
    ".ogg": "audio_url", ".m4a": "audio_url",
    # Images
    ".jpg": "image", ".jpeg": "image", ".png": "image",
    ".gif": "image", ".webp": "image", ".svg": "image",
    # Documents
    ".pdf": "pdf",
    ".docx": "office_doc", ".xlsx": "office_doc", ".pptx": "office_doc",
    ".doc": "office_doc", ".xls": "office_doc",
    ".md": "markdown", ".mdx": "markdown",
    ".html": "html_doc", ".htm": "html_doc",
    # Structured
    ".json": "json", ".xml": "xml",
    ".csv": "csv", ".tsv": "csv",
    ".yaml": "yaml", ".yml": "yaml",
    # Code
    ".py": "code", ".ts": "code", ".js": "code", ".go": "code",
    ".rs": "code", ".java": "code", ".ipynb": "code",
    # Logs
    ".log": "log_file",
    # Spatial
    ".pcd": "lidar", ".las": "lidar",
    ".geojson": "geospatial", ".kml": "geospatial", ".shp": "geospatial",
    ".gltf": "model_3d", ".glb": "model_3d", ".obj": "model_3d", ".stl": "model_3d",
    # Communication
    ".ics": "calendar", ".eml": "email",
    # Archives
    ".zip": "archive", ".tar": "archive", ".gz": "archive", ".bz2": "archive",
    # Medical
    ".dcm": "medical_imaging",
}

AGENT_FALLBACK_KEY: str = "binary_blob"
# When url is present but data is not downloaded, route to this agent first.
DOWNLOAD_AGENT_KEY: str = "url_download"

# Keys that belong in meta_data when normalizing (rest go into data).
# Uses the comprehensive set from meta_schema plus nested group keys.
_ROUTER_KNOWN_META_KEYS = _KNOWN_FLAT_KEYS | frozenset({
    "identity", "content", "access", "tracing", "routing",
})

# Plan 3 — UDE source_type → agent_type mapping (Layer 0a)
SOURCE_TYPE_AGENT_MAP: dict[str, str] = {
    "chat": "channel_message",
    "email": "email",
    "conferencing": "conferencing",
    "document": "pdf",
    "image": "image",
    "video": "video_url",
    "audio": "audio_url",
    "code": "code",
    "vehicle": "vehicle_telemetry",
    "satellite": "satellite",
    "sensor": "iot_sensor",
    "telemetry": "iot_sensor",
    "geospatial": "geospatial",
    "medical": "medical_imaging",
    "financial": "financial",
    "scientific": "scientific",
    "industrial": "industrial",
    "infrastructure": "infrastructure",
    "binary": "binary_blob",
    "other": "binary_blob",
}


def normalize_message(payload: dict) -> tuple[dict, dict]:
    """Normalize to (data, meta_data). Accepts data+meta_data, data+telemetry, or flat format.

    Prefers "meta_data" over "telemetry" when both present. Known meta keys at
    top level are merged into the chosen bucket.  The result meta_data is always
    in nested group format.

    Returns:
        (data, meta_data) for downstream use.
    """
    if not isinstance(payload, dict):
        return (payload if isinstance(payload, dict) else {"raw": str(payload)}), {}

    has_data = "data" in payload and isinstance(payload.get("data"), dict)
    meta_bucket = None
    if has_data:
        if "meta_data" in payload and isinstance(payload.get("meta_data"), dict):
            meta_bucket = dict(payload.get("meta_data") or {})
        elif "telemetry" in payload and isinstance(payload.get("telemetry"), dict):
            meta_bucket = dict(payload.get("telemetry") or {})

    if has_data and meta_bucket is not None:
        data = payload.get("data")
        meta = meta_bucket
        for k in _ROUTER_KNOWN_META_KEYS:
            if k in payload and k not in meta:
                meta[k] = payload[k]
        return data, normalize_meta_data(meta)

    meta_flat: dict = {k: payload[k] for k in _ROUTER_KNOWN_META_KEYS if k in payload}
    data = {k: v for k, v in payload.items() if k not in _ROUTER_KNOWN_META_KEYS}
    return data, normalize_meta_data(meta_flat)


def _detect_by_explicit_field(payload: dict) -> str | None:
    """Layer 1: check ``data_type`` / ``source_type`` for a direct match."""
    for field in ("data_type", "source_type", "type"):
        value = payload.get(field)
        if value and isinstance(value, str):
            key = value.strip().lower()
            if key in AGENT_REGISTRY:
                return key
    return None


def _detect_by_mime(payload: dict) -> str | None:
    """Layer 3: match ``content_type`` / ``media_type`` via the MIME registry."""
    mime = payload.get("content_type") or payload.get("media_type") or ""
    if not mime:
        return None
    agent = MIME_REGISTRY.match(mime.strip().lower())
    return agent.AGENT_TYPE if agent else None


def _detect_by_url_extension(payload: dict) -> str | None:
    """Layer 4: sniff the ``url`` field for a known file extension."""
    url: str = payload.get("url") or payload.get("source_url") or ""
    if not url:
        return None
    # Strip query string / fragment before checking extension
    path = url.split("?")[0].split("#")[0].lower()
    for ext, agent_type in _EXT_MAP.items():
        if path.endswith(ext):
            return agent_type
    return None


# ---------------------------------------------------------------------------
# Payload field heuristic → agent_type mapping (Layer 2)
# ---------------------------------------------------------------------------

# Each entry: (set of indicator keys, agent_type, min_matches)
# If the payload contains at least `min_matches` of the indicator keys, it
# maps to that agent_type.  Checked in order; first match wins.
_FIELD_HEURISTICS: list[tuple[frozenset[str], str, int]] = [
    # Email
    (frozenset({"from", "to", "subject", "body", "cc", "bcc", "envelope_id"}), "email", 3),
    # Calendar / events
    (frozenset({"dtstart", "dtend", "rrule", "icalendar", "event_start", "event_end", "attendees", "organizer"}), "calendar", 2),
    # Chat / messaging
    (frozenset({"sender", "message", "channel", "thread_id", "chat_id", "reply_to"}), "chat", 2),
    # Conferencing
    (frozenset({"meeting_id", "participants", "transcript", "recording_url", "conference_url"}), "conferencing", 2),
    # Video
    (frozenset({"video_url", "video_data", "frame_rate", "frames", "duration", "resolution", "codec"}), "video_url", 2),
    # Audio
    (frozenset({"audio_url", "audio_data", "sample_rate", "channels", "bitrate", "waveform"}), "audio_url", 2),
    # Image
    (frozenset({"image_url", "image_data", "width", "height", "pixels", "exif", "thumbnail"}), "image", 2),
    # Image batch
    (frozenset({"images", "image_list", "image_urls", "batch_id"}), "image_batch", 2),
    # PDF
    (frozenset({"pdf_url", "pdf_data", "pages", "page_count", "pdf_text"}), "pdf", 2),
    # Office docs
    (frozenset({"docx_url", "xlsx_url", "pptx_url", "sheets", "slides", "document_text"}), "office_doc", 2),
    # Markdown
    (frozenset({"markdown", "md_content", "frontmatter"}), "markdown", 1),
    # HTML
    (frozenset({"html", "html_content", "dom", "stylesheet"}), "html_doc", 1),
    # Code
    (frozenset({"code", "source_code", "language", "repository", "commit", "diff", "ast"}), "code", 2),
    # Log file
    (frozenset({"log_file", "log_path", "log_entries", "log_level", "log_lines"}), "log_file", 2),
    # Log stream
    (frozenset({"log_stream", "stream_id", "severity", "log_name"}), "log_stream", 2),
    # GPS / location
    (frozenset({"latitude", "longitude", "lat", "lng", "lon", "coordinates", "altitude", "heading", "speed"}), "gps", 2),
    # Geospatial
    (frozenset({"geojson", "geometry", "features", "crs", "bbox", "projection"}), "geospatial", 1),
    # LiDAR
    (frozenset({"point_cloud", "lidar_data", "points", "pcd_url", "las_url", "scan_id"}), "lidar", 2),
    # 3D model
    (frozenset({"mesh", "vertices", "faces", "gltf", "glb_url", "obj_url", "model_3d"}), "model_3d", 2),
    # IoT sensor
    (frozenset({"sensor_id", "sensor_type", "device_id", "telemetry", "readings"}), "iot_sensor", 2),
    # Biometric
    (frozenset({"heart_rate", "blood_pressure", "spo2", "biometric", "ecg", "hrv"}), "biometric", 2),
    # Generic sensor (temperature/humidity/pressure without sensor_id)
    (frozenset({"temperature", "humidity", "pressure", "acceleration", "gyroscope", "magnetometer"}), "sensor", 2),
    # Vehicle telemetry
    (frozenset({"vehicle_id", "vin", "odometer", "engine_rpm", "fuel_level", "obd", "can_bus"}), "vehicle_telemetry", 2),
    # Satellite
    (frozenset({"satellite_id", "orbit", "tle", "pass_time", "band", "swath"}), "satellite", 2),
    # Medical imaging
    (frozenset({"dicom", "patient_id", "modality", "study_id", "series_id", "medical_image"}), "medical_imaging", 2),
    # Financial
    (frozenset({"amount", "currency", "transaction_id", "account", "balance", "ticker", "portfolio"}), "financial", 2),
    # Scientific
    (frozenset({"experiment", "hypothesis", "observations", "specimen", "reagent", "protocol"}), "scientific", 2),
    # Industrial
    (frozenset({"machine_id", "plc", "scada", "production_line", "cycle_time", "downtime"}), "industrial", 2),
    # Infrastructure
    (frozenset({"host", "cpu_usage", "memory_usage", "disk_usage", "network", "uptime", "container_id"}), "infrastructure", 2),
    # Time series
    (frozenset({"timestamps", "values", "series", "time_series", "interval", "frequency"}), "time_series", 2),
    # Feed (RSS/Atom)
    (frozenset({"feed_url", "entries", "published", "author", "feed_title", "rss", "atom"}), "feed", 2),
    # Web page
    (frozenset({"page_url", "page_title", "page_content", "links", "meta_tags"}), "web_page", 2),
    # Archive
    (frozenset({"archive_url", "archive_data", "entries", "compressed", "archive_type"}), "archive", 2),
    # CSV
    (frozenset({"csv_data", "csv_url", "columns", "rows", "delimiter", "header"}), "csv", 2),
    # XML
    (frozenset({"xml_data", "xml_url", "root_element", "namespace", "schema"}), "xml", 2),
    # YAML
    (frozenset({"yaml_data", "yaml_url", "yaml_content"}), "yaml", 1),
    # JSON (very generic — only match on explicit json indicators)
    (frozenset({"json_data", "json_url", "json_schema", "json_content"}), "json", 1),
]


def _detect_by_payload_fields(payload: dict) -> str | None:
    """Layer 2: inspect payload key names to heuristically determine agent type."""
    if not isinstance(payload, dict):
        return None
    keys = set(payload.keys())
    # Also check keys of nested dicts one level deep for richer signal
    for v in payload.values():
        if isinstance(v, dict):
            keys.update(v.keys())
    keys_lower = {k.lower() for k in keys}
    for indicator_keys, agent_type, min_matches in _FIELD_HEURISTICS:
        if len(keys_lower & indicator_keys) >= min_matches:
            if agent_type in AGENT_REGISTRY:
                return agent_type
    return None


def _detect_by_channel_message(meta_data: dict) -> str | None:
    """Layer 0 — if meta_data carries a channel_message, route to channel_message agent."""
    ch_msg = get_channel_message(meta_data)
    if isinstance(ch_msg, dict) and ch_msg.get("channel_type"):
        if "channel_message" in AGENT_REGISTRY:
            return "channel_message"
    return None


def _detect_by_source_type(meta_data: dict) -> str | None:
    """Layer 0a — map UDE source_type from meta_data to agent_type."""
    source_type = str(get_source_type(meta_data) or "").lower()
    if not source_type:
        return None
    agent_type = SOURCE_TYPE_AGENT_MAP.get(source_type)
    if agent_type and agent_type in AGENT_REGISTRY:
        return agent_type
    return None


def detect_data_type(payload: dict, meta_data: dict | None = None) -> tuple[str, str]:
    """Run all detection layers and return the agent type plus the layer that matched.

    Detection order:
    0.  Channel message shortcut (meta_data carries ``channel_message``).
    0a. UDE source_type from meta_data.
    1.  Explicit field (``data_type`` / ``source_type`` in payload).
    2.  Payload field heuristic (key name pattern matching).
    3.  MIME registry.
    4.  URL extension sniff.
    5.  Fallback → binary_blob.

    Args:
        payload: The decoded webhook payload dict (``data`` section).
        meta_data: Optional meta_data dict (receiver-injected).

    Returns:
        A tuple of ``(agent_type, detection_layer)`` where *agent_type* is
        guaranteed to exist in ``AGENT_REGISTRY``.
    """
    meta_data = meta_data or {}

    # Layer 0 — channel message shortcut (Plan 2)
    result = _detect_by_channel_message(meta_data)
    if result:
        logger.debug("Layer 0 (channel_message) matched: %s", result)
        return result, "channel_message"

    # Layer 0a — UDE source_type (Plan 3)
    result = _detect_by_source_type(meta_data)
    if result:
        logger.debug("Layer 0a (source_type) matched: %s", result)
        return result, "source_type"

    # Layer 1 — explicit field
    result = _detect_by_explicit_field(payload)
    if result:
        logger.debug("Layer 1 matched: %s", result)
        return result, "explicit_field"

    # Layer 2 — payload field heuristic (no AI model needed)
    result = _detect_by_payload_fields(payload)
    if result:
        logger.debug("Layer 2 (field heuristic) matched: %s", result)
        return result, "field_heuristic"

    # Layer 3 — MIME registry (check both data and meta_data)
    result = _detect_by_mime(payload)
    if not result and meta_data:
        mime_from_meta = get_mime_type(meta_data) or ""
        if mime_from_meta:
            agent = MIME_REGISTRY.match(mime_from_meta.strip().lower())
            if agent:
                result = agent.AGENT_TYPE
    if result:
        logger.debug("Layer 3 (MIME) matched: %s", result)
        return result, "mime"

    # Layer 4 — URL extension
    result = _detect_by_url_extension(payload)
    if result:
        logger.debug("Layer 4 (URL ext) matched: %s", result)
        return result, "url_ext"

    logger.debug("No layer matched; using fallback: %s", AGENT_FALLBACK_KEY)
    return AGENT_FALLBACK_KEY, "fallback"


def route_payload(payload_json: str) -> dict[str, Any]:
    """Detect payload type, resolve group context, and dispatch to sub-agent.

    This is the main entry point called by the ADK agent's ``route_data``
    tool.  The full pipeline is:

    1. Pop ``__trace_context__`` from the payload (injected by the processor).
    2. Detect data type (four layers).
    3. Resolve / ensure group memories.
    4. Write the raw record (``write_record``).
    5. Stage, analyse, and enrich the record (``process``).

    Two OTel spans are written to the inherited ``trace_memory_id``:

    * ``webhook.agent``        — SERVER — covers the entire function.
    * ``webhook.agent.router`` — INTERNAL — covers detection + dispatch
      (child of the agent span).

    Args:
        payload_json: The incoming webhook payload as a JSON string.

    Returns:
        A routing result dict containing ``data_type``, group context
        fields, the agent's publish manifest, the write record result
        under ``record``, and the process/enrich result under ``process``.
    """
    agent_start = datetime.now(timezone.utc)

    try:
        payload: dict = json.loads(payload_json)
    except (json.JSONDecodeError, ValueError):
        payload = {"raw": payload_json}

    # Normalize to data + meta_data
    data, meta_data = normalize_message(payload)
    if "meta_data" not in payload or "data" not in payload:
        payload = {"data": data, "meta_data": meta_data}
    # Ensure data_id from data is in meta_data so write_record/process see it (e.g. API forward).
    if data.get("data_id") and not get_data_id(meta_data):
        set_field(meta_data, "access", "data_id", data["data_id"])

    # Enforce canonical EventMeta defaults: user_id must always be present.
    from .api_client.config import AGENT_USER_ID as _default_user
    if not get_user_id(meta_data):
        uid = (
            (data.get("origin") or {}).get("user_id")
            or data.get("user_id")
            or _default_user
        )
        set_field(meta_data, "identity", "user_id", uid)
    # Propagate version fields from data block if not in meta
    if not get_version(meta_data) and data.get("version"):
        set_field(meta_data, "tracing", "version", data["version"])
    if not get_version_label(meta_data) and data.get("version_label"):
        set_field(meta_data, "tracing", "version_label", data["version_label"])
    if not get_data_id(meta_data) and data.get("data_id"):
        set_field(meta_data, "access", "data_id", data["data_id"])

    # Pop trace context (injected by processor or upstream)
    trace_ctx: dict = meta_data.pop("__trace_context__", {}) or {}
    trace_id: str = trace_ctx.get("trace_id") or (
        uuid.uuid4().hex + uuid.uuid4().hex[:0] or uuid.uuid4().hex
    )
    processor_span_id: str | None = trace_ctx.get("span_id") or trace_ctx.get("parent_span_id") or None
    agent_span_id: str = uuid.uuid4().hex[:16]
    router_span_id: str = uuid.uuid4().hex[:16]

    # Ensure a tracing memory exists so spans appear in the Telemetry UI.
    # Upstream (processor / API ingest) may provide one; if not, create it here.
    if not get_trace_memory_id(meta_data) and not trace_ctx.get("trace_memory_id"):
        try:
            created_id = memory_client.create_tracing_memory(
                user_id=get_user_id(meta_data) or _default_user,
            )
            set_field(meta_data, "tracing", "trace_memory_id", created_id)
            logger.info("Created tracing memory for webhook: %s", created_id)
        except Exception as exc:
            logger.warning("Failed to create tracing memory: %s", exc)
    elif trace_ctx.get("trace_memory_id") and not get_trace_memory_id(meta_data):
        set_field(meta_data, "tracing", "trace_memory_id", trace_ctx["trace_memory_id"])

    # Rebuild payload for downstream (data + meta_data, no __trace_context__)
    clean_payload_json = json.dumps({"data": data, "meta_data": meta_data})

    # Write an early "PROCESSING" agent span so tracing is visible immediately.
    _early_trace_memory_id = get_trace_memory_id(meta_data)
    _early_user_id = get_user_id(meta_data)
    if trace_id and _early_trace_memory_id:
        try:
            tracking_client.write_span(
                trace_id=trace_id,
                span_id=agent_span_id,
                name="webhook.agent",
                stage="agent",
                service_name=_AGENT_SERVICE,
                service_type=_AGENT_SERVICE_TYPE,
                status_code="PROCESSING",
                kind="SERVER",
                start_time=agent_start,
                end_time=datetime.now(timezone.utc),
                parent_span_id=processor_span_id,
                trace_memory_id=_early_trace_memory_id,
                user_id=_early_user_id,
                attributes={"phase": "started"},
            )
        except Exception:
            pass  # best-effort

    try:
        router_start = datetime.now(timezone.utc)

        # Detect data type from content (data) + meta_data
        data_type, detection_layer = detect_data_type(data, meta_data)
        agent = AGENT_REGISTRY.get(data_type, AGENT_REGISTRY[AGENT_FALLBACK_KEY])

        # Layer 0b — route to download when payload has url but data is not yet
        # downloaded (no data_id or is_downloaded=false).
        if get_url(meta_data) and not (
            get_data_id(meta_data) and get_is_downloaded(meta_data)
        ):
            if DOWNLOAD_AGENT_KEY in AGENT_REGISTRY:
                agent = AGENT_REGISTRY[DOWNLOAD_AGENT_KEY]
                logger.debug(
                    "Layer 0b (url_download): routing to download agent for url=%s",
                    (get_url(meta_data) or "")[:80],
                )

        # Resolve and ensure group memories (user/group from data, channel from meta_data)
        group_ctx = ensure_group_memories(
            build_group_context(data, meta_data),
            agent_instance_id=agent.instance_id,
        )

        # Build dataset-classification tags so every stored record carries
        # enough metadata to interpret the data without inspecting the payload.
        classification_tags: list[str] = [f"detected_by:{detection_layer}"]
        raw_mime: str = (
            data.get("content_type") or data.get("media_type") or ""
        ).strip().lower()
        if raw_mime:
            classification_tags.append(f"mime_type:{raw_mime}")
            mime_category = raw_mime.split("/")[0]
            if mime_category:
                classification_tags.append(f"mime_category:{mime_category}")

        # Sub-agent trace context — agent span is parent of sub-agent spans
        sub_trace_ctx = {
            "trace_id": trace_id,
            "parent_span_id": router_span_id,
        }

        # When data_id and is_downloaded are in meta_data (e.g. API forward), skip write — content already stored.
        if get_data_id(meta_data) and get_is_downloaded(meta_data):
            record = {"status": "success", "data_id": get_data_id(meta_data)}
        else:
            record = agent.write_record(
                payload_json=json.dumps(data),
                name=f"{data_type}-event",
                group_context=group_ctx,
                extra_tags=classification_tags,
                trace_context=sub_trace_ctx,
                meta_data=meta_data,
            )
        if record.get("status") == "success" and record.get("data_id"):
            set_field(meta_data, "access", "data_id", record["data_id"])

        # Stage → analyse → viewpoint → embedding (pass data content for processing)
        process_result: dict[str, Any] = {"status": "skipped", "reason": "write_record failed"}
        if record.get("status") == "success":
            payload_meta = {
                "detection_layer": detection_layer,
                "mime_type": raw_mime or get_mime_type(meta_data) or "",
                "is_downloaded": get_is_downloaded(meta_data),
                "data_id": record.get("data_id"),
                "prompt": get_prompt(meta_data),
                "url": get_url(meta_data),
                "download_url": get_download_url(meta_data),
                "gcs_uri": get_gcs_uri(meta_data),
                "user_id": get_user_id(meta_data),
            }

            # Write early sub-agent "PROCESSING" span
            subagent_span_id = uuid.uuid4().hex[:16]
            subagent_start = datetime.now(timezone.utc)
            if trace_id and get_trace_memory_id(meta_data):
                try:
                    tracking_client.write_span(
                        trace_id=trace_id,
                        span_id=subagent_span_id,
                        name=f"webhook.subagent.{agent.AGENT_TYPE}",
                        stage="subagent",
                        service_name=f"subagent-{agent.AGENT_TYPE}",
                        service_type="gcp_cloud_run_adk",
                        status_code="PROCESSING",
                        kind="INTERNAL",
                        start_time=subagent_start,
                        end_time=datetime.now(timezone.utc),
                        parent_span_id=router_span_id,
                        trace_memory_id=get_trace_memory_id(meta_data),
                        user_id=get_user_id(meta_data) or group_ctx.user_id,
                        data_id=record.get("data_id"),
                        attributes={"agent_type": agent.AGENT_TYPE, "phase": "started"},
                    )
                except Exception:
                    pass

            if not _is_processing_enabled(agent.AGENT_TYPE, get_user_id(meta_data)):
                logger.info(
                    "AI processing disabled for agent_type=%s user=%s — skipping",
                    agent.AGENT_TYPE, get_user_id(meta_data),
                )
                process_result = {
                    "status": "skipped",
                    "reason": "ai_processing_disabled",
                    "agent_type": agent.AGENT_TYPE,
                    "data_id": record.get("data_id"),
                }
            else:
                try:
                    process_result = agent.process(
                        payload_json=json.dumps(data),
                        data_id=record["data_id"],
                        group_context=group_ctx,
                        payload_meta=payload_meta,
                        trace_context=sub_trace_ctx,
                    )
                except Exception as exc:
                    logger.warning(
                        "process() raised for %s / %s: %s",
                        data_type, record.get("data_id"), exc,
                    )
                    process_result = {
                        "status": "error",
                        "agent_type": data_type,
                        "data_id": record.get("data_id"),
                        "error": str(exc),
                    }

            # Write final sub-agent span with actual status
            if trace_id and get_trace_memory_id(meta_data):
                try:
                    tracking_client.write_span(
                        trace_id=trace_id,
                        span_id=subagent_span_id,
                        name=f"webhook.subagent.{agent.AGENT_TYPE}",
                        stage="subagent",
                        service_name=f"subagent-{agent.AGENT_TYPE}",
                        service_type="gcp_cloud_run_adk",
                        status_code="OK" if process_result.get("status") in ("success", "skipped") else "ERROR",
                        kind="INTERNAL",
                        start_time=subagent_start,
                        end_time=datetime.now(timezone.utc),
                        parent_span_id=router_span_id,
                        trace_memory_id=get_trace_memory_id(meta_data),
                        user_id=get_user_id(meta_data) or group_ctx.user_id,
                        data_id=record.get("data_id"),
                        mime_type=raw_mime or None,
                        attributes={
                            "agent_type": agent.AGENT_TYPE,
                            "instance_id": agent.instance_id,
                            "process_status": process_result.get("status"),
                        },
                    )
                except Exception:
                    pass

        router_end = datetime.now(timezone.utc)

        logger.info(
            "Routed payload",
            extra={
                "data_type": data_type,
                "agent_instance_id": agent.instance_id,
                "is_new_group": group_ctx.is_new_group,
                "group_timeline": group_ctx.timeline_memory_id,
                "process_status": process_result.get("status"),
                "trace_id": trace_id,
            },
        )

        # Write router span (INTERNAL, child of agent span)
        tracking_client.write_span(
            trace_id=trace_id,
            span_id=router_span_id,
            name="webhook.agent.router",
            stage="router",
            service_name=_AGENT_SERVICE,
            service_type=_AGENT_SERVICE_TYPE,
            status_code="OK",
            kind="INTERNAL",
            start_time=router_start,
            end_time=router_end,
            parent_span_id=agent_span_id,
            trace_memory_id=get_trace_memory_id(meta_data),
            user_id=get_user_id(meta_data) or group_ctx.user_id,
            data_id=record.get("data_id"),
            version=get_version(meta_data),
            mime_type=raw_mime or None,
            attributes={
                "data_type": data_type,
                "detection_layer": detection_layer,
                "group_timeline": group_ctx.timeline_memory_id,
                "group_session": group_ctx.session_memory_id,
                "group_id": group_ctx.group_id,
                "is_new_group": group_ctx.is_new_group,
                "process_status": process_result.get("status"),
                "agent_instance_id": agent.instance_id,
                "agent_type": agent.AGENT_TYPE,
            },
        )

        agent_end = datetime.now(timezone.utc)

        # Write agent span (SERVER, child of processor span)
        tracking_client.write_span(
            trace_id=trace_id,
            span_id=agent_span_id,
            name="webhook.agent",
            stage="agent",
            service_name=_AGENT_SERVICE,
            service_type=_AGENT_SERVICE_TYPE,
            status_code="OK",
            kind="SERVER",
            start_time=agent_start,
            end_time=agent_end,
            parent_span_id=processor_span_id,
            trace_memory_id=get_trace_memory_id(meta_data),
            user_id=get_user_id(meta_data),
            data_id=record.get("data_id"),
            version=get_version(meta_data),
            mime_type=raw_mime or None,
            attributes={
                "data_type": data_type,
                "detection_layer": detection_layer,
                "payload_size_bytes": len(payload_json),
                "process_status": process_result.get("status"),
            },
        )

        return {
            "data_type": data_type,
            "is_new_group": group_ctx.is_new_group,
            "prefix": group_ctx.prefix,
            "user_id": group_ctx.user_id,
            "group_id": group_ctx.group_id,
            "group_timeline": group_ctx.timeline_memory_id,
            "group_session": group_ctx.session_memory_id,
            "agent": agent.publish(),
            "record": record,
            "process": process_result,
        }

    except Exception as exc:
        agent_end = datetime.now(timezone.utc)
        _err_mime = (
            (data.get("content_type") or data.get("media_type") or "").strip().lower()
            if isinstance(data, dict) else ""
        ) or None
        tracking_client.write_span(
            trace_id=trace_id,
            span_id=agent_span_id,
            name="webhook.agent",
            stage="agent",
            service_name=_AGENT_SERVICE,
            service_type=_AGENT_SERVICE_TYPE,
            status_code="ERROR",
            kind="SERVER",
            start_time=agent_start,
            end_time=agent_end,
            parent_span_id=processor_span_id,
            trace_memory_id=get_trace_memory_id(meta_data),
            user_id=get_user_id(meta_data),
            data_id=get_data_id(meta_data),
            version=get_version(meta_data),
            mime_type=_err_mime,
            attributes={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "payload_keys": list(payload.keys()) if isinstance(payload, dict) else [],
            },
        )
        raise
