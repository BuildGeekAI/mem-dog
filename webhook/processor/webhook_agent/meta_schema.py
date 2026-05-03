"""Canonical meta_data schema: nested groups, normalization, and accessors.

After the telemetry → meta_data rename, meta_data fields are organized into
five logical groups:

* **identity** — ``user_id``, ``owner``
* **content**  — ``mime_type``, ``source_type``, ``channel_message``
* **access**   — ``data_id``, ``url``, ``download_url``, ``gcs_uri``, ``is_downloaded``
* **tracing**  — ``trace_memory_id``, ``memory``, ``session_id``, ``version``, ``version_label``
* **routing**  — ``prompt``, ``crawl``

``__trace_context__`` remains at the top level of ``meta_data``.

This module provides:
- ``normalize_meta_data()`` — migrates flat meta_data to nested format
- Typed accessor helpers that work on both flat (legacy) and nested meta_data
- ``build_meta_data()`` — factory for building fresh nested meta_data
- ``set_field()`` — safe nested setter
- ``_KNOWN_FLAT_KEYS`` — union of all flat keys for receiver/processor normalization
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Flat key → (group, key) mapping for backward compatibility
# ---------------------------------------------------------------------------

_FLAT_TO_GROUP: dict[str, tuple[str, str]] = {
    # identity
    "user_id": ("identity", "user_id"),
    "owner": ("identity", "owner"),
    # content
    "mime_type": ("content", "mime_type"),
    "mimetype": ("content", "mime_type"),  # legacy alias
    "source_type": ("content", "source_type"),
    "channel_message": ("content", "channel_message"),
    # access
    "data_id": ("access", "data_id"),
    "url": ("access", "url"),
    "download_url": ("access", "download_url"),
    "gcs_uri": ("access", "gcs_uri"),
    "is_downloaded": ("access", "is_downloaded"),
    # tracing
    "trace_memory_id": ("tracing", "trace_memory_id"),
    "memory": ("tracing", "memory"),
    "memory_list": ("tracing", "memory"),  # legacy alias → merged into memory
    "session_id": ("tracing", "session_id"),
    "version": ("tracing", "version"),
    "version_label": ("tracing", "version_label"),
    # routing
    "prompt": ("routing", "prompt"),
    "crawl": ("routing", "crawl"),
}

# Fields that are removed (dead / duplicated in data.payload)
_REMOVED_FIELDS: frozenset[str] = frozenset({
    "user_name", "name", "description", "tags", "subject",
    "llm_classification", "participants", "envelope_id",
    "timestamp", "services", "device",
})

# All flat keys recognized by receiver/processor for splitting data vs meta
_KNOWN_FLAT_KEYS: frozenset[str] = frozenset(
    set(_FLAT_TO_GROUP.keys())
    | {"__trace_context__"}
    | _REMOVED_FIELDS
    # Keep these so old payloads with them are still split correctly
    | {"memory_list"}
)

# The five group names
_GROUPS = ("identity", "content", "access", "tracing", "routing")


# ---------------------------------------------------------------------------
# normalize_meta_data — flat → nested migration
# ---------------------------------------------------------------------------

def normalize_meta_data(meta: dict) -> dict:
    """Auto-migrate a flat meta_data dict to the nested group structure.

    If *meta* already contains nested group keys (``identity``, ``content``,
    etc.) they are preserved.  Flat keys are mapped into their group.  Removed
    fields are dropped.  ``mimetype`` is merged into ``content.mime_type``.
    ``memory_list`` is merged into ``tracing.memory`` (converted to dict if needed).

    ``__trace_context__`` is preserved at the top level.

    Returns a new dict (does not mutate *meta*).
    """
    result: dict[str, Any] = {}

    # Preserve existing nested groups
    for grp in _GROUPS:
        if grp in meta and isinstance(meta[grp], dict):
            result[grp] = dict(meta[grp])

    # Preserve __trace_context__ at top level
    if "__trace_context__" in meta:
        result["__trace_context__"] = meta["__trace_context__"]

    # Migrate flat keys
    for key, value in meta.items():
        if key in _GROUPS or key == "__trace_context__":
            continue  # already handled
        if key in _REMOVED_FIELDS:
            continue  # drop

        mapping = _FLAT_TO_GROUP.get(key)
        if mapping is None:
            # Unknown key — preserve at top level for forward compat
            result[key] = value
            continue

        group, target_key = mapping

        result.setdefault(group, {})

        # Special handling: memory_list → tracing.memory
        if key == "memory_list":
            if "memory" not in result[group]:
                # Convert flat list to dict format if it's a list
                if isinstance(value, list):
                    result[group]["memory"] = {"other": value}
                elif isinstance(value, dict):
                    result[group]["memory"] = value
            continue

        # Special handling: mimetype → content.mime_type (don't overwrite existing)
        if key == "mimetype":
            if "mime_type" not in result[group]:
                result[group]["mime_type"] = value
            continue

        # Don't overwrite values already set from nested groups
        if target_key not in result[group]:
            result[group][target_key] = value

    return result


# ---------------------------------------------------------------------------
# Accessor helpers — work on both flat and nested meta_data
# ---------------------------------------------------------------------------

def _get(meta: dict, group: str, key: str, default: Any = None) -> Any:
    """Get a value from nested or flat meta_data."""
    # Try nested first
    grp = meta.get(group)
    if isinstance(grp, dict):
        val = grp.get(key)
        if val is not None:
            return val
    # Fall back to flat
    val = meta.get(key)
    if val is not None:
        return val
    return default


def get_user_id(meta: dict) -> str | None:
    return _get(meta, "identity", "user_id")


def get_owner(meta: dict) -> dict | None:
    return _get(meta, "identity", "owner")


def get_mime_type(meta: dict) -> str | None:
    val = _get(meta, "content", "mime_type")
    if val is not None:
        return val
    # Legacy alias
    return meta.get("mimetype")


def get_source_type(meta: dict) -> str | None:
    return _get(meta, "content", "source_type")


def get_channel_message(meta: dict) -> dict | None:
    return _get(meta, "content", "channel_message")


def get_data_id(meta: dict) -> str | None:
    return _get(meta, "access", "data_id")


def get_url(meta: dict) -> str | None:
    return _get(meta, "access", "url")


def get_download_url(meta: dict) -> str | None:
    return _get(meta, "access", "download_url")


def get_gcs_uri(meta: dict) -> str | None:
    return _get(meta, "access", "gcs_uri")


def get_is_downloaded(meta: dict) -> bool:
    return bool(_get(meta, "access", "is_downloaded", False))


def get_trace_memory_id(meta: dict) -> str | None:
    return _get(meta, "tracing", "trace_memory_id")


def get_memory(meta: dict) -> dict | None:
    val = _get(meta, "tracing", "memory")
    if isinstance(val, dict):
        return val
    return None


def get_session_id(meta: dict) -> str | None:
    return _get(meta, "tracing", "session_id")


def get_version(meta: dict) -> int | None:
    val = _get(meta, "tracing", "version")
    return int(val) if val is not None else None


def get_version_label(meta: dict) -> str | None:
    return _get(meta, "tracing", "version_label")


def get_prompt(meta: dict) -> str | None:
    return _get(meta, "routing", "prompt")


def get_crawl(meta: dict) -> dict | None:
    return _get(meta, "routing", "crawl")


# ---------------------------------------------------------------------------
# set_field — safe nested setter
# ---------------------------------------------------------------------------

def set_field(meta: dict, group: str, key: str, value: Any) -> None:
    """Set a value in the nested meta_data structure (mutates *meta*)."""
    meta.setdefault(group, {})[key] = value


# ---------------------------------------------------------------------------
# build_meta_data — factory
# ---------------------------------------------------------------------------

def build_meta_data(
    *,
    user_id: str | None = None,
    owner: dict | None = None,
    mime_type: str | None = None,
    source_type: str | None = None,
    channel_message: dict | None = None,
    data_id: str | None = None,
    url: str | None = None,
    download_url: str | None = None,
    gcs_uri: str | None = None,
    is_downloaded: bool = False,
    trace_memory_id: str | None = None,
    memory: dict | None = None,
    session_id: str | None = None,
    version: int | None = None,
    version_label: str | None = None,
    prompt: str | None = None,
    crawl: dict | None = None,
    trace_context: dict | None = None,
) -> dict:
    """Build a fresh nested meta_data dict from keyword arguments.

    Only non-None values are included (except ``is_downloaded`` which defaults
    to False and is always included in ``access``).
    """
    result: dict[str, Any] = {}

    # identity
    identity: dict[str, Any] = {}
    if user_id is not None:
        identity["user_id"] = user_id
    if owner is not None:
        identity["owner"] = owner
    if identity:
        result["identity"] = identity

    # content
    content: dict[str, Any] = {}
    if mime_type is not None:
        content["mime_type"] = mime_type
    if source_type is not None:
        content["source_type"] = source_type
    if channel_message is not None:
        content["channel_message"] = channel_message
    if content:
        result["content"] = content

    # access
    access: dict[str, Any] = {"is_downloaded": is_downloaded}
    if data_id is not None:
        access["data_id"] = data_id
    if url is not None:
        access["url"] = url
    if download_url is not None:
        access["download_url"] = download_url
    if gcs_uri is not None:
        access["gcs_uri"] = gcs_uri
    result["access"] = access

    # tracing
    tracing: dict[str, Any] = {}
    if trace_memory_id is not None:
        tracing["trace_memory_id"] = trace_memory_id
    if memory is not None:
        tracing["memory"] = memory
    if session_id is not None:
        tracing["session_id"] = session_id
    if version is not None:
        tracing["version"] = version
    if version_label is not None:
        tracing["version_label"] = version_label
    if tracing:
        result["tracing"] = tracing

    # routing
    routing: dict[str, Any] = {}
    if prompt is not None:
        routing["prompt"] = prompt
    if crawl is not None:
        routing["crawl"] = crawl
    if routing:
        result["routing"] = routing

    # trace context at top level
    if trace_context is not None:
        result["__trace_context__"] = trace_context

    return result
