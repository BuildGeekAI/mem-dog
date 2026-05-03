"""Group context for correlating related payloads.

When a series of payloads belong to the same logical unit (an order, a
batch job, a user session) they should share the same timeline and session
memories so all data can be queried together.

The **prefix** is the primary grouping handle — a short, caller-supplied
string (e.g. ``"ord-42"``) that maps deterministically to memory IDs.
When no prefix is provided, the group is derived from ``user_id`` and
the first correlation-style field found in the payload.

Memory ID formation
-------------------
* With prefix     → ``timeline-{prefix}``  /  ``session-{prefix}``
* Derived (group) → ``timeline-grp-{user_id}-{group_id[:12]}``
* Derived (user)  → ``timeline-grp-{user_id}``
"""

import logging
import re
from dataclasses import asdict, dataclass

from .api_client.config import AGENT_USER_ID
from .meta_schema import get_channel_message, get_owner, get_user_id

logger = logging.getLogger("mem_dog.webhook.group_context")

# Fields checked (in order) for an explicit prefix
_PREFIX_FIELDS = ("memory_prefix", "prefix", "group_prefix", "bucket_prefix")

# Fields checked (in order) for the owner user identity
_USER_ID_FIELDS = ("user_id", "userId", "user", "owner", "sender", "from_user")

# Fields checked (in order) for a correlation / group identifier
_GROUP_ID_FIELDS = (
    "correlation_id",
    "group_id",
    "session_id",
    "batch_id",
    "trace_id",
    "conversation_id",
    "request_id",
)

# Characters allowed in a prefix / memory ID
_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9\-_]")


def _sanitise(value: str) -> str:
    """Replace characters unsafe for memory IDs with hyphens."""
    return _SAFE_PATTERN.sub("-", value).strip("-")[:64]


def extract_prefix(payload: dict) -> str | None:
    """Extract an explicit memory-grouping prefix from *payload*.

    Checks ``memory_prefix``, ``prefix``, ``group_prefix``, and
    ``bucket_prefix`` in that order.

    Args:
        payload: The decoded webhook payload dict.

    Returns:
        Sanitised prefix string, or ``None`` if none found.
    """
    for field in _PREFIX_FIELDS:
        value = payload.get(field)
        if value and isinstance(value, str):
            sanitised = _sanitise(value)
            if sanitised:
                return sanitised
    return None


def extract_group_ids(payload: dict, meta_data: dict | None = None) -> tuple[str, str]:
    """Extract ``(user_id, group_id)`` from *payload* and *meta_data*.

    Checks ``meta_data["user_id"]`` and nested ``meta_data["owner"]["user"]["user_id"]``
    in addition to flat fields in the data payload.

    Falls back to ``AGENT_USER_ID`` if no user field is found.
    Falls back to ``user_id`` as the group if no group field is found.

    Args:
        payload: The decoded webhook payload dict (data section).
        meta_data: Optional telemetry / meta_data section.

    Returns:
        A ``(user_id, group_id)`` tuple of sanitised strings.
    """
    meta_data = meta_data or {}
    user_id = AGENT_USER_ID

    # 1. Check meta_data user_id (supports both flat and nested)
    meta_uid = get_user_id(meta_data)
    if meta_uid and isinstance(meta_uid, str):
        user_id = _sanitise(meta_uid)
    else:
        # 2. Check nested owner in meta_data
        owner = get_owner(meta_data)
        owner_uid = ((owner or {}).get("user") or {}).get("user_id")
        if owner_uid and isinstance(owner_uid, str):
            user_id = _sanitise(str(owner_uid))
        else:
            # 3. Fall back to flat fields in the data payload
            for field in _USER_ID_FIELDS:
                value = payload.get(field)
                if value and isinstance(value, str):
                    user_id = _sanitise(value)
                    break

    group_id = user_id
    for field in _GROUP_ID_FIELDS:
        value = payload.get(field)
        if value and isinstance(value, str):
            group_id = _sanitise(value)
            break

    return user_id, group_id


@dataclass
class GroupContext:
    """Holds the resolved group identity and its memory IDs.

    Attributes:
        prefix: Explicit caller-supplied prefix, or ``None``.
        user_id: Resolved owner of the data.
        group_id: Resolved group scope (may equal ``user_id``).
        timeline_memory_id: The timeline memory to write into.
        session_memory_id: The session memory to write into.
        is_new_group: ``True`` when the memories were just created.
        owner: Plan 1 — DataOwner-compatible dict extracted from the payload.
        channel_type: Plan 2 — Channel type string (e.g. ``"whatsapp"``).
        channel_peer_id: Plan 2 — Sender identifier on the channel.
        channel_thread_id: Plan 2 — Thread / reply chain ID.
        conversation_memory_id: Plan 2 — Conversation memory ID (if any).
    """

    prefix: str | None
    user_id: str
    group_id: str
    timeline_memory_id: str
    session_memory_id: str
    is_new_group: bool = False
    # Plan 1 — provenance
    owner: dict | None = None
    # Plan 2 — channel context
    channel_type: str | None = None
    channel_peer_id: str | None = None
    channel_thread_id: str | None = None
    conversation_memory_id: str | None = None

    def as_dict(self) -> dict:
        """Return a plain dict representation."""
        return asdict(self)


def build_group_context(payload: dict, meta_data: dict | None = None) -> GroupContext:
    """Construct a :class:`GroupContext` from a decoded payload.

    This is the **single entry point** for the router.  It tries the
    prefix path first; if no prefix is found it falls back to the
    derived user+group path.

    Plan 1 & 2: ``meta_data`` is checked for ``owner`` and
    ``channel_message`` dicts injected by the receiver so channel
    context is threaded all the way to sub-agents.

    Args:
        payload: The decoded webhook payload dict (``data`` section).
        meta_data: Optional ``meta_data`` section from the canonical
            ``{data, meta_data}`` envelope (receiver-injected fields).

    Returns:
        A :class:`GroupContext` with ``is_new_group=False``
        (call :func:`ensure_group_memories` to set the flag).
    """
    meta_data = meta_data or {}
    prefix = extract_prefix(payload)
    user_id, group_id = extract_group_ids(payload, meta_data)

    # Plan 1 — pull owner from meta_data (injected by receiver)
    owner: dict | None = get_owner(meta_data) or None

    # Plan 2 — pull channel context from channel_message in meta_data
    channel_type: str | None = None
    channel_peer_id: str | None = None
    channel_thread_id: str | None = None
    conversation_memory_id: str | None = None

    ch_msg = get_channel_message(meta_data)
    if isinstance(ch_msg, dict):
        channel_type = ch_msg.get("channel_type")
        channel_peer_id = ch_msg.get("peer_id")
        channel_thread_id = ch_msg.get("thread_id")
        conv_id = ch_msg.get("thread_id") or ch_msg.get("channel_id") or group_id
        if conv_id:
            conversation_memory_id = f"conversation-{_sanitise(str(conv_id))}"

    if prefix:
        return GroupContext(
            prefix=prefix,
            user_id=user_id,
            group_id=group_id,
            timeline_memory_id=f"timeline-{prefix}",
            session_memory_id=f"session-{prefix}",
            owner=owner,
            channel_type=channel_type,
            channel_peer_id=channel_peer_id,
            channel_thread_id=channel_thread_id,
            conversation_memory_id=conversation_memory_id,
        )

    group_key = f"{user_id}-{group_id[:12]}" if group_id != user_id else user_id
    return GroupContext(
        prefix=None,
        user_id=user_id,
        group_id=group_id,
        timeline_memory_id=f"timeline-grp-{group_key}",
        session_memory_id=f"session-grp-{group_key}",
        owner=owner,
        channel_type=channel_type,
        channel_peer_id=channel_peer_id,
        channel_thread_id=channel_thread_id,
        conversation_memory_id=conversation_memory_id,
    )


def ensure_group_memories(ctx: GroupContext, agent_instance_id: str = "router") -> GroupContext:
    """Return group context without creating any group memories in memdog.

    Memory-creation policy: only **data-processing** memories (stored data
    items) and **telemetry** memories (tracing, pipeline telemetry) are
    created on the API/webhook path.  Agents do not create group timeline
    or session memories.  When the UI client sends a message, the UI may
    create its own memory (the UI's memory, recorded in the session); that
    is separate from the API receiving data.

    This function still returns a :class:`GroupContext` with the same
    ``timeline_memory_id`` and ``session_memory_id`` (from
    :func:`build_group_context`) for use in routing and metadata; those
    memory containers are simply never created by the agent.

    Args:
        ctx: The :class:`GroupContext` returned by :func:`build_group_context`.
        agent_instance_id: Unused; kept for API compatibility.

    Returns:
        A new :class:`GroupContext` with ``is_new_group=False``.
    """
    return GroupContext(
        prefix=ctx.prefix,
        user_id=ctx.user_id,
        group_id=ctx.group_id,
        timeline_memory_id=ctx.timeline_memory_id,
        session_memory_id=ctx.session_memory_id,
        is_new_group=False,
        owner=ctx.owner,
        channel_type=ctx.channel_type,
        channel_peer_id=ctx.channel_peer_id,
        channel_thread_id=ctx.channel_thread_id,
        conversation_memory_id=ctx.conversation_memory_id,
    )
