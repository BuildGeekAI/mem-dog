"""ULID-based ID generation with prefixes.

All data is stored in Postgres. New IDs use ULIDs (Universally Unique
Lexicographically Sortable Identifiers) with prefixes: data_ for data items,
mem_<type> for memories (e.g. mem_timeline, mem_session, mem_telemetry, mem_tracing,
mem_custom). Existing IDs (UUID or legacy) remain valid.
"""

from ulid import ULID


def generate_data_id() -> str:
    """Return a new data ID with prefix data_."""
    return f"data_{ULID()}"


def generate_memory_id(memory_type: str) -> str:
    """Return a new memory ID with prefix mem_<type>.

    memory_type should be the string value of MemoryType (e.g. timeline, session,
    telemetry, tracing, custom).
    """
    safe_type = (memory_type or "custom").lower().replace(" ", "_")
    return f"mem_{safe_type}_{ULID()}"


def generate_webhook_id() -> str:
    """Return a new webhook ID with prefix whk_."""
    return f"whk_{ULID()}"


def generate_event_id() -> str:
    """Return a new webhook event ID with prefix evt_."""
    return f"evt_{ULID()}"
