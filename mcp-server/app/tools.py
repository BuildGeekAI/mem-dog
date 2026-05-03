"""MCP tool implementations backed by the mem-dog API."""

from __future__ import annotations

import json
from typing import Any

import httpx

from mem_dog_client.simple import MemDog


async def tool_search(
    client: MemDog,
    query: str,
    max_results: int = 5,
    search_mode: str = "hybrid",
) -> str:
    """Semantic/hybrid search across stored data."""
    async with httpx.AsyncClient(
        base_url=client._client._base,
        headers={"Authorization": f"Bearer {client._client._api_key}"},
        timeout=60.0,
    ) as http:
        resp = await http.post(
            "/api/v1/ai/query/semantic",
            json={
                "query": query,
                "max_results": max_results,
                "search_mode": search_mode,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    records = data.get("records", [])
    if not records:
        return "No results found."

    lines = []
    for r in records:
        chunks = r.get("matching_chunks", [])
        best = chunks[0]["text"] if chunks else ""
        sim = chunks[0].get("similarity", 0) if chunks else 0
        lines.append(
            f"- **{r.get('name', r.get('data_id', '?'))}** "
            f"(id: {r.get('data_id', '?')}, similarity: {sim:.3f})\n  {best[:300]}"
        )
    header = f"Found {len(records)} results for \"{query}\":"
    if data.get("answer"):
        header += f"\n\n**AI Summary:** {data['answer']}"
    return header + "\n\n" + "\n\n".join(lines)


async def tool_add(
    client: MemDog,
    content: str,
    name: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None,
    memory_type: str | None = None,
    memory_id: str | None = None,
) -> str:
    """Store text content with optional tags and memory association."""
    result = client.add(
        content,
        name=name,
        tags=tags,
        description=description,
        memory_type=memory_type,
        memory_id=memory_id,
    )
    return json.dumps(result)


async def tool_get(client: MemDog, data_id: str) -> str:
    """Retrieve a data item by ID."""
    result = client.get(data_id)
    content = result.get("content", "")
    if isinstance(content, dict):
        content = json.dumps(content, indent=2)
    elif isinstance(content, str) and len(content) > 2000:
        content = content[:2000] + "... (truncated)"

    meta_lines = []
    for key in ("name", "tags", "created_at", "content_type"):
        if key in result and result[key]:
            meta_lines.append(f"**{key}:** {result[key]}")

    header = f"**Data ID:** {data_id}"
    if meta_lines:
        header += "\n" + "\n".join(meta_lines)
    return f"{header}\n\n{content}"


async def tool_delete(client: MemDog, data_id: str) -> str:
    """Delete a data item."""
    client.delete(data_id)
    return f"Deleted {data_id}"


async def tool_entities(
    client: MemDog,
    query: str,
    entity_type: str | None = None,
    limit: int = 20,
) -> str:
    """Search knowledge graph entities."""
    results = client.entities(query, entity_type=entity_type, limit=limit)
    if not results:
        return "No entities found."

    lines = []
    for e in results:
        etype = e.get("entity_type", "unknown")
        name = e.get("name", e.get("entity_id", "?"))
        lines.append(f"- **{name}** (type: {etype}, id: {e.get('entity_id', '?')})")
    return f"Found {len(results)} entities:\n\n" + "\n".join(lines)


async def tool_chat(
    client: MemDog,
    message: str,
    history: list[dict[str, str]] | None = None,
    max_results: int = 5,
    search_mode: str = "hybrid",
) -> str:
    """RAG conversational query with citations."""
    payload: dict[str, Any] = {
        "message": message,
        "max_results": max_results,
        "search_mode": search_mode,
    }
    if history:
        payload["history"] = history

    async with httpx.AsyncClient(
        base_url=client._client._base,
        headers={"Authorization": f"Bearer {client._client._api_key}"},
        timeout=60.0,
    ) as http:
        resp = await http.post("/api/v1/ai/query/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

    answer = data.get("answer", "No answer generated.")
    citations = data.get("citations", [])
    if citations:
        cite_lines = []
        for c in citations:
            cite_lines.append(
                f"  [{c.get('index', '?')}] {c.get('name', c.get('data_id', '?'))}"
            )
        answer += "\n\n**Sources:**\n" + "\n".join(cite_lines)
    return answer


async def tool_memories(
    client: MemDog,
    action: str = "list",
    memory_type: str | None = None,
    name: str | None = None,
    limit: int = 20,
) -> str:
    """List or create memories."""
    low_level = client.client

    if action == "create":
        if not memory_type:
            return "Error: memory_type is required when action='create'"
        payload: dict[str, Any] = {"memory_type": memory_type}
        if name:
            payload["name"] = name
        resp = low_level.create_memory(payload)
        resp.raise_for_status()
        return json.dumps(resp.json())

    # Default: list
    resp = low_level.list_memories(memory_type=memory_type, limit=limit)
    resp.raise_for_status()
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])

    if not items:
        return "No memories found."

    lines = []
    for m in items:
        mid = m.get("memory_id") or m.get("id", "?")
        mtype = m.get("memory_type", "?")
        mname = m.get("name", "")
        lines.append(f"- **{mname or mid}** (type: {mtype}, id: {mid})")
    return f"Found {len(items)} memories:\n\n" + "\n".join(lines)


async def tool_list_data(
    client: MemDog,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """List stored data items."""
    resp = client.client.list_user_data(format="meta", limit=limit, offset=offset)
    resp.raise_for_status()
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])

    if not items:
        return "No data items found."

    lines = []
    for item in items:
        did = item.get("data_id") or item.get("id", "?")
        name = item.get("name", "")
        tags = item.get("tags", [])
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        lines.append(f"- **{name or did}**{tag_str} (id: {did})")
    return f"Found {len(items)} items:\n\n" + "\n".join(lines)
