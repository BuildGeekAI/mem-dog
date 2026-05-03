"""OpenAI function-calling adapter for memdog memory.

Provides tool definitions and a handler for OpenAI's function calling API,
enabling any OpenAI-compatible agent to use memdog as persistent memory.

Usage::

    from mem_dog_client.adapters.openai import get_mem_dog_tools, handle_mem_dog_tool_call
    from mem_dog_client import MemDog

    m = MemDog("http://localhost:8080", user_id="user1")
    tools = get_mem_dog_tools()

    # In your OpenAI chat loop:
    response = client.chat.completions.create(messages=messages, tools=tools)
    for call in response.choices[0].message.tool_calls:
        result = handle_mem_dog_tool_call(m, call.function.name, json.loads(call.function.arguments))
"""

from __future__ import annotations

import json
from typing import Any, Optional

from mem_dog_client.simple import MemDog


def get_mem_dog_tools() -> list[dict[str, Any]]:
    """Return OpenAI-compatible tool definitions for memdog operations."""
    return [
        {
            "type": "function",
            "function": {
                "name": "mem_dog_save",
                "description": "Save information to persistent memory for later retrieval.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The text content to save to memory.",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags to categorize the content.",
                        },
                    },
                    "required": ["content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mem_dog_search",
                "description": "Search persistent memory for relevant information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default 5).",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mem_dog_get",
                "description": "Retrieve a specific memory item by its ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_id": {
                            "type": "string",
                            "description": "The data item ID to retrieve.",
                        },
                    },
                    "required": ["data_id"],
                },
            },
        },
    ]


def handle_mem_dog_tool_call(
    mem_dog: MemDog,
    function_name: str,
    arguments: dict[str, Any],
) -> str:
    """Handle a memdog tool call and return the result as a JSON string.

    Args:
        mem_dog: A configured MemDog instance.
        function_name: The function name from the tool call.
        arguments: The parsed arguments dict.

    Returns:
        JSON string with the result (for passing back to OpenAI as tool output).
    """
    if function_name == "mem_dog_save":
        result = mem_dog.add(
            content=arguments["content"],
            tags=arguments.get("tags"),
        )
        return json.dumps(result)

    elif function_name == "mem_dog_search":
        results = mem_dog.search(
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )
        return json.dumps(results, default=str)

    elif function_name == "mem_dog_get":
        result = mem_dog.get(data_id=arguments["data_id"])
        return json.dumps(result, default=str)

    else:
        return json.dumps({"error": f"Unknown function: {function_name}"})
