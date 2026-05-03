"""MCP Server instance with tool registrations."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from app.auth import require_client
from app.tools import (
    tool_add,
    tool_chat,
    tool_delete,
    tool_entities,
    tool_get,
    tool_list_data,
    tool_memories,
    tool_search,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mem-dog",
    instructions=(
        "mem-dog is a private AI memory and knowledge platform. "
        "Use these tools to search, store, retrieve, and manage data and memories."
    ),
)


@mcp.tool()
async def search(
    query: str,
    max_results: int = 5,
    search_mode: str = "hybrid",
) -> str:
    """Search stored data using semantic, keyword, or hybrid search.

    Args:
        query: Natural language search query
        max_results: Maximum number of results (1-20, default 5)
        search_mode: Search strategy - "vector" (semantic), "fts" (keyword), "hybrid" (both), "graph" (knowledge graph), "full" (all signals)
    """
    return await tool_search(require_client(), query, max_results, search_mode)


@mcp.tool()
async def add(
    content: str,
    name: str = "",
    tags: str = "",
    description: str = "",
    memory_type: str = "",
    memory_id: str = "",
) -> str:
    """Store text content in mem-dog with optional metadata.

    Args:
        content: The text content to store
        name: Human-readable name for the data item
        tags: Comma-separated tags (e.g. "notes,meeting,project-x")
        description: Optional description of the content
        memory_type: Auto-create and attach to a memory of this type (e.g. "conversation", "session", "user", "factual")
        memory_id: Attach to an existing memory by ID instead
    """
    return await tool_add(
        require_client(),
        content,
        name=name or None,
        tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else None,
        description=description or None,
        memory_type=memory_type or None,
        memory_id=memory_id or None,
    )


@mcp.tool()
async def get(data_id: str) -> str:
    """Retrieve a data item by its ID.

    Args:
        data_id: The data item ID (e.g. "data_01HXYZ...")
    """
    return await tool_get(require_client(), data_id)


@mcp.tool()
async def delete(data_id: str) -> str:
    """Delete a data item by its ID.

    Args:
        data_id: The data item ID to delete
    """
    return await tool_delete(require_client(), data_id)


@mcp.tool()
async def entities(
    query: str,
    entity_type: str = "",
    limit: int = 20,
) -> str:
    """Search knowledge graph entities (people, organizations, concepts, etc.).

    Args:
        query: Search text matched against entity names
        entity_type: Filter by type (e.g. "person", "organization", "concept")
        limit: Maximum results (default 20)
    """
    return await tool_entities(
        require_client(), query, entity_type=entity_type or None, limit=limit
    )


@mcp.tool()
async def chat(
    message: str,
    search_mode: str = "hybrid",
    max_results: int = 5,
) -> str:
    """Ask a question and get an AI-generated answer with citations from your stored data.

    Args:
        message: Your question or message
        search_mode: Search strategy - "vector", "fts", "hybrid", "graph", "full"
        max_results: Number of source documents to consider (default 5)
    """
    return await tool_chat(
        require_client(), message, max_results=max_results, search_mode=search_mode
    )


@mcp.tool()
async def memories(
    action: str = "list",
    memory_type: str = "",
    name: str = "",
    limit: int = 20,
) -> str:
    """List or create memories. Memories are containers that group related data items.

    Args:
        action: "list" to browse memories, "create" to make a new one
        memory_type: Filter by type when listing, or type for new memory. Types: timeline, session, conversation, user, organizational, factual, episodic, semantic, custom, tracing
        name: Name for a new memory (used with action="create")
        limit: Max memories to return when listing (default 20)
    """
    return await tool_memories(
        require_client(),
        action=action,
        memory_type=memory_type or None,
        name=name or None,
        limit=limit,
    )


@mcp.tool()
async def list_data(limit: int = 20, offset: int = 0) -> str:
    """List your stored data items with metadata.

    Args:
        limit: Maximum items to return (default 20)
        offset: Skip this many items for pagination (default 0)
    """
    return await tool_list_data(require_client(), limit=limit, offset=offset)
