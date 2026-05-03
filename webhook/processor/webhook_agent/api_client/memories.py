"""Memory API client.

Handles creating and retrieving mem-dog memories.  Absorbed the
``_ensure_memory`` / ``_ensure_agent_memories`` helpers that previously
lived in ``agent.py`` so they are reusable across the whole agent package.
"""

import logging

from .config import AGENT_USER_ID, DEFAULT_TIMEOUT, MEM_DOG_API_URL
from .session import _session

logger = logging.getLogger("mem_dog.webhook.api_client.memories")


class MemoryClient:
    """Thin wrapper around the /api/v1/memories endpoint."""

    def __init__(self, base_url: str = MEM_DOG_API_URL) -> None:
        self._base = f"{base_url}/api/v1/memories"

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def ensure(
        self,
        memory_id: str,
        memory_type: str,
        name: str,
        description: str,
        agent_instance_id: str,
        user_id: str = AGENT_USER_ID,
    ) -> str:
        """Ensure a memory exists, creating it if needed.

        Idempotent — safe to call on every request.

        Args:
            memory_id: Stable identifier for the memory.
            memory_type: ``"timeline"`` or ``"session"``.
            name: Human-readable name stored on the memory.
            description: Description stored on the memory.
            agent_instance_id: Used to populate metadata for traceability.
            user_id: Owner of the memory.

        Returns:
            The ``memory_id`` (same value passed in).

        Raises:
            requests.RequestException: If an unexpected API error occurs.
        """
        try:
            resp = _session.get(f"{self._base}/{memory_id}", timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 200:
                return memory_id
        except Exception:
            pass

        payload = {
            "memory_id": memory_id,
            "memory_type": memory_type,
            "name": name,
            "description": description,
            "user_id": user_id,
            "metadata": {
                "source": "webhook_agent",
                "agent_instance_id": agent_instance_id,
                "auto_created": True,
            },
        }
        resp = _session.post(self._base, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        created_id: str = resp.json().get("memory_id", memory_id)
        logger.info("Created %s memory: %s", memory_type, created_id)
        return created_id

    def ensure_pair(self, instance_id: str, user_id: str = AGENT_USER_ID) -> tuple[str, str]:
        """Ensure both timeline and session memories exist for an agent instance.

        Args:
            instance_id: Unique agent instance identifier used to name the memories.
            user_id: Owner of the memories.

        Returns:
            A ``(timeline_memory_id, session_memory_id)`` tuple.

        Raises:
            requests.RequestException: If either API call fails.
        """
        timeline_id = self.ensure(
            memory_id=f"timeline-{instance_id}",
            memory_type="timeline",
            name=f"Agent ({instance_id})",
            description=f"Timeline for agent instance {instance_id}",
            agent_instance_id=instance_id,
            user_id=user_id,
        )
        session_id = self.ensure(
            memory_id=f"session-{instance_id}",
            memory_type="session",
            name=f"Agent Session ({instance_id})",
            description=f"Active session for agent instance {instance_id}",
            agent_instance_id=instance_id,
            user_id=user_id,
        )
        return timeline_id, session_id

    def create_tracing_memory(self, user_id: str = AGENT_USER_ID) -> str:
        """Create a per-invocation tracing memory (type ``tracing``).

        Does not pass ``memory_id`` so the API generates a ULID-prefixed id
        (e.g. ``mem_tracing_<ulid>``).  Used so each webhook invocation can
        store its OTel spans in a dedicated trace memory.

        Returns:
            The created memory_id from the API response.
        """
        payload = {
            "memory_type": "tracing",
            "name": "Webhook trace",
            "description": "Per-invocation trace container for OTel spans",
            "user_id": user_id,
            "metadata": {"source": "webhook_agent", "auto_created": True},
        }
        resp = _session.post(self._base, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        created_id: str = resp.json().get("memory_id", "")
        if not created_id:
            raise ValueError("API did not return memory_id")
        logger.info("Created tracing memory: %s", created_id)
        return created_id

    def ensure_group_pair(
        self,
        timeline_memory_id: str,
        session_memory_id: str,
        user_id: str,
        group_id: str,
        agent_instance_id: str,
    ) -> tuple[str, bool]:
        """Ensure a group-scoped timeline + session memory pair exist.

        Args:
            timeline_memory_id: Desired memory ID for the group timeline.
            session_memory_id: Desired memory ID for the group session.
            user_id: Owner of the group.
            group_id: Group identifier (for naming / description).
            agent_instance_id: Agent instance creating the group.

        Returns:
            A ``(timeline_memory_id, is_new)`` tuple where ``is_new`` is
            ``True`` when the timeline memory did not previously exist.
        """
        try:
            resp = _session.get(
                f"{self._base}/{timeline_memory_id}", timeout=DEFAULT_TIMEOUT
            )
            already_exists = resp.status_code == 200
        except Exception:
            already_exists = False

        if not already_exists:
            self.ensure(
                memory_id=timeline_memory_id,
                memory_type="timeline",
                name=f"Group Timeline ({group_id})",
                description=f"Shared timeline for group {group_id} owned by {user_id}",
                agent_instance_id=agent_instance_id,
                user_id=user_id,
            )
            self.ensure(
                memory_id=session_memory_id,
                memory_type="session",
                name=f"Group Session ({group_id})",
                description=f"Shared session for group {group_id} owned by {user_id}",
                agent_instance_id=agent_instance_id,
                user_id=user_id,
            )

        return timeline_memory_id, not already_exists
