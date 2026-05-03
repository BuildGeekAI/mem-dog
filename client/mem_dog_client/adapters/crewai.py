"""CrewAI adapter for mem-dog memory.

Provides ``MemDogCrewMemory`` with ``save()`` and ``search()`` methods
compatible with CrewAI's memory interface.

Usage::

    from mem_dog_client.adapters.crewai import MemDogCrewMemory
    from mem_dog_client import MemDog

    m = MemDog("http://localhost:8080", user_id="user1")
    memory = MemDogCrewMemory(m)
    memory.save("Meeting notes about Q1 results", metadata={"topic": "finance"})
    results = memory.search("Q1 results")

Requires: ``pip install crewai`` (optional — works standalone too)
"""

from __future__ import annotations

from typing import Any, Optional

from mem_dog_client.simple import MemDog


class MemDogCrewMemory:
    """CrewAI-compatible memory backed by mem-dog.

    Implements ``save()`` and ``search()`` which map to ``MemDog.add()``
    and ``MemDog.search()`` respectively.
    """

    def __init__(
        self,
        mem_dog: MemDog,
        memory_type: str = "session",
        user_id: Optional[str] = None,
    ) -> None:
        self._md = mem_dog
        self._memory_type = memory_type
        self._user_id = user_id

    def save(
        self,
        content: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Save content to mem-dog.

        Args:
            content: Text content to store.
            metadata: Optional metadata (stored as tags).
            tags: Optional tags.

        Returns:
            ``{"data_id": "...", "memory_id": "..."}``
        """
        all_tags = list(tags or [])
        if metadata:
            for k, v in metadata.items():
                all_tags.append(f"{k}:{v}")

        return self._md.add(
            content=content,
            tags=all_tags,
            memory_type=self._memory_type,
            user_id=self._user_id,
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        use_ai: bool = False,
    ) -> list[dict[str, Any]]:
        """Search mem-dog memory.

        Args:
            query: Search query text.
            limit: Maximum results.
            use_ai: Use AI-powered RAG query.

        Returns:
            List of result dicts.
        """
        return self._md.search(
            query,
            limit=limit,
            use_ai=use_ai,
            user_id=self._user_id,
        )

    def reset(self) -> None:
        """No-op — mem-dog doesn't support bulk memory reset."""
        pass
