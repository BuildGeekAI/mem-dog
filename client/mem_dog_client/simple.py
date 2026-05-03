"""Simplified memdog client.

Provides a high-level ``MemDog`` facade with four methods —
``add()``, ``search()``, ``get()``, ``delete()`` — that orchestrate
the lower-level ``MemDogClient`` REST calls.
"""

from __future__ import annotations

from datetime import date
from typing import Any, BinaryIO, Optional

from mem_dog_client.client import MemDogClient


class MemDog:
    """High-level memdog client.

    Example::

        m = MemDog("http://localhost:8080", api_key="my-key")
        result = m.add("Hello world", tags=["greeting"])
        print(result["data_id"])

        results = m.search("hello", limit=5)
        item = m.get(result["data_id"])
        m.delete(result["data_id"])
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        self._client = MemDogClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            **kwargs,
        )
        self._user_id = user_id

    # ------------------------------------------------------------------
    # add
    # ------------------------------------------------------------------

    def add(
        self,
        content: Optional[str] = None,
        *,
        file: Optional[BinaryIO] = None,
        tags: Optional[list[str]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        memory_type: Optional[str] = None,
        memory_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Store content and optionally attach it to a memory.

        Args:
            content: Text content to store.
            file: Binary file object to upload (mutually exclusive with *content*).
            tags: Optional tags to attach.
            name: Human-readable name for the data item.
            description: Optional description.
            memory_type: If set and *memory_id* is ``None``, auto-create a
                memory of this type (e.g. ``"conversation"``, ``"session"``).
            memory_id: Existing memory ID to attach the data to.
            user_id: Override the default user_id.

        Returns:
            ``{"data_id": "...", "memory_id": "..." | None}``
        """
        uid = user_id or self._user_id

        # 1. Create the data item
        create_kwargs: dict[str, Any] = {}
        if content is not None:
            create_kwargs["content"] = content
        if file is not None:
            create_kwargs["file"] = file
        if tags:
            create_kwargs["tags"] = tags
        if name:
            create_kwargs["name"] = name
        if description:
            create_kwargs["description"] = description
        if memory_id:
            create_kwargs["memory_ids"] = [memory_id]

        resp = self._client.create_data(**create_kwargs)
        resp.raise_for_status()
        data = resp.json()
        data_id = data.get("data_id") or data.get("id")

        result: dict[str, Any] = {"data_id": data_id, "memory_id": memory_id}

        # 2. Auto-create memory if memory_type given but no memory_id
        if memory_type and not memory_id:
            mem_name = f"auto-{memory_type}-{date.today().isoformat()}"
            # Try to find existing auto-memory for today
            existing_mid = self._find_auto_memory(memory_type, mem_name, uid)
            if existing_mid:
                mid = existing_mid
            else:
                mem_payload: dict[str, Any] = {
                    "memory_type": memory_type,
                    "name": mem_name,
                }
                if uid:
                    mem_payload["user_id"] = uid
                mem_resp = self._client.create_memory(mem_payload)
                mem_resp.raise_for_status()
                mem_data = mem_resp.json()
                mid = mem_data.get("memory_id") or mem_data.get("id")

            # Attach data to memory
            if mid and data_id:
                attach_resp = self._client.add_data_to_memory(mid, [data_id])
                attach_resp.raise_for_status()
            result["memory_id"] = mid

        return result

    def _find_auto_memory(
        self, memory_type: str, name: str, user_id: Optional[str]
    ) -> Optional[str]:
        """Find an existing auto-memory by name for today."""
        try:
            resp = self._client.list_memories(
                memory_type=memory_type,
                user_id=user_id or None,
                limit=50,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else data.get("items", [])
            for mem in items:
                if mem.get("name") == name:
                    return mem.get("memory_id") or mem.get("id")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        memory_type: Optional[str] = None,
        memory_ids: Optional[list[str]] = None,
        use_ai: bool = False,
        user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search stored data.

        Args:
            query: Search query text.
            limit: Maximum results to return.
            memory_type: Filter by memory type.
            memory_ids: Scope search to specific memories.
            use_ai: If ``True``, use the AI-powered RAG query endpoint.
            user_id: Override the default user_id.

        Returns:
            List of result dicts. Structure depends on *use_ai*:
            - ``use_ai=False``: ``[{"data_id", "name", "tags", ...}, ...]``
            - ``use_ai=True``: ``[{"response", "sources", "model", ...}]``
        """
        uid = user_id or self._user_id

        if use_ai:
            kwargs: dict[str, Any] = {"query": query}
            if memory_ids:
                kwargs["memory_ids"] = memory_ids
            resp = self._client.ai_query(**kwargs)
            resp.raise_for_status()
            data = resp.json()
            # Wrap single response in a list for consistency
            return [data] if isinstance(data, dict) else data

        if memory_type:
            resp = self._client.list_memories(
                memory_type=memory_type,
                user_id=uid,
                limit=limit,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else data.get("items", [])
            return items[:limit]

        resp = self._client.list_user_data(
            user=uid,
            format="meta",
            limit=limit,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        return items

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    def get(
        self,
        data_id: str,
        *,
        version: Optional[int] = None,
    ) -> dict[str, Any]:
        """Retrieve a data item with its content and metadata.

        Args:
            data_id: The data item ID.
            version: Optional version number (defaults to latest).

        Returns:
            ``{"data_id", "content", "name", "tags", "created_at", ...}``
        """
        # Fetch content
        content_resp = self._client.get_data(data_id, version=version)
        content_resp.raise_for_status()

        content_type = content_resp.headers.get("content-type", "")
        if "json" in content_type:
            content = content_resp.json()
        else:
            content = content_resp.text

        # Fetch metadata
        try:
            meta_resp = self._client.get_metadata(data_id)
            meta_resp.raise_for_status()
            meta = meta_resp.json()
        except Exception:
            meta = {}

        result: dict[str, Any] = {"data_id": data_id}
        if isinstance(meta, dict):
            result.update(meta)
        result["content"] = content
        return result

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    def delete(self, data_id: str) -> bool:
        """Delete a data item.

        Args:
            data_id: The data item ID to delete.

        Returns:
            ``True`` if deleted successfully.
        """
        resp = self._client.delete_data(data_id)
        resp.raise_for_status()
        return True

    # ------------------------------------------------------------------
    # Graph Memory
    # ------------------------------------------------------------------

    def entities(
        self,
        query: str,
        *,
        entity_type: Optional[str] = None,
        limit: int = 20,
        user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search entities in the knowledge graph.

        Args:
            query: Search text (matched against entity names).
            entity_type: Filter by type (person, organization, etc.).
            limit: Maximum results.
            user_id: Override the default user_id.

        Returns:
            List of entity dicts.
        """
        uid = user_id or self._user_id or ""
        resp = self._client.search_entities(query, user_id=uid, entity_type=entity_type, limit=limit)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def related(
        self,
        data_id: str,
        *,
        user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get entities extracted from a data item.

        Args:
            data_id: The data item ID.
            user_id: Override the default user_id.

        Returns:
            List of entity dicts linked to this data item.
        """
        uid = user_id or self._user_id or ""
        resp = self._client.get_data_entities(data_id, user_id=uid)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Memory Compression
    # ------------------------------------------------------------------

    def compress(
        self,
        memory_id: str,
        *,
        archive_originals: bool = False,
        max_summary_length: int = 2000,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Compress a memory's data items into a summary.

        Args:
            memory_id: The memory to compress.
            archive_originals: If True, tag originals as archived and unlink.
            max_summary_length: Max chars for the summary.
            user_id: Override the default user_id.

        Returns:
            ``{"memory_id", "summary_data_id", "original_count", "summary_length", "archived"}``
        """
        uid = user_id or self._user_id or ""
        resp = self._client.compress_memory(
            memory_id, user_id=uid,
            archive_originals=archive_originals,
            max_summary_length=max_summary_length,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Low-level access
    # ------------------------------------------------------------------

    @property
    def client(self) -> MemDogClient:
        """Access the underlying ``MemDogClient`` for advanced operations."""
        return self._client
