"""Unit tests for MCP tool implementations with respx mocks."""

import json

import httpx
import pytest
import respx

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


@pytest.mark.asyncio
async def test_search(client):
    with respx.mock:
        respx.post("http://testserver:8080/api/v1/ai/query/semantic").mock(
            return_value=httpx.Response(
                200,
                json={
                    "query": "test",
                    "records": [
                        {
                            "data_id": "data_001",
                            "name": "Test Doc",
                            "matching_chunks": [
                                {"text": "Hello world", "similarity": 0.95}
                            ],
                        }
                    ],
                    "latency_ms": 42,
                },
            )
        )
        result = await tool_search(client, "test", max_results=5)
        assert "Test Doc" in result
        assert "data_001" in result
        assert "0.950" in result


@pytest.mark.asyncio
async def test_search_no_results(client):
    with respx.mock:
        respx.post("http://testserver:8080/api/v1/ai/query/semantic").mock(
            return_value=httpx.Response(
                200, json={"query": "nothing", "records": [], "latency_ms": 10}
            )
        )
        result = await tool_search(client, "nothing")
        assert "No results" in result


@pytest.mark.asyncio
async def test_add(client):
    with respx.mock:
        respx.post("http://testserver:8080/api/v1/data").mock(
            return_value=httpx.Response(200, json={"data_id": "data_new"})
        )
        result = await tool_add(client, "Hello", name="greeting", tags=["test"])
        parsed = json.loads(result)
        assert parsed["data_id"] == "data_new"


@pytest.mark.asyncio
async def test_get(client):
    with respx.mock:
        respx.get("http://testserver:8080/api/v1/data/data_001").mock(
            return_value=httpx.Response(
                200, text="File content here", headers={"content-type": "text/plain"}
            )
        )
        respx.get("http://testserver:8080/api/v1/data/data_001/metadata").mock(
            return_value=httpx.Response(
                200, json={"name": "My File", "tags": ["doc"]}
            )
        )
        result = await tool_get(client, "data_001")
        assert "data_001" in result
        assert "My File" in result
        assert "File content here" in result


@pytest.mark.asyncio
async def test_delete(client):
    with respx.mock:
        respx.delete("http://testserver:8080/api/v1/data/data_001").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await tool_delete(client, "data_001")
        assert "Deleted" in result


@pytest.mark.asyncio
async def test_entities(client):
    with respx.mock:
        respx.get("http://testserver:8080/api/v1/graph/entities").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "entity_id": "ent_1",
                        "name": "Acme Corp",
                        "entity_type": "organization",
                    }
                ],
            )
        )
        result = await tool_entities(client, "acme")
        assert "Acme Corp" in result
        assert "organization" in result


@pytest.mark.asyncio
async def test_chat(client):
    with respx.mock:
        respx.post("http://testserver:8080/api/v1/ai/query/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "answer": "The answer is 42.",
                    "citations": [
                        {"index": 1, "data_id": "data_001", "name": "Guide"}
                    ],
                    "latency_ms": 100,
                },
            )
        )
        result = await tool_chat(client, "What is the answer?")
        assert "42" in result
        assert "Guide" in result


@pytest.mark.asyncio
async def test_memories_list(client):
    with respx.mock:
        respx.get("http://testserver:8080/api/v1/memories").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "memory_id": "mem_conv_001",
                            "memory_type": "conversation",
                            "name": "Chat session",
                        }
                    ]
                },
            )
        )
        result = await tool_memories(client, action="list")
        assert "Chat session" in result
        assert "conversation" in result


@pytest.mark.asyncio
async def test_memories_create(client):
    with respx.mock:
        respx.post("http://testserver:8080/api/v1/memories").mock(
            return_value=httpx.Response(
                200, json={"memory_id": "mem_fact_001", "memory_type": "factual"}
            )
        )
        result = await tool_memories(
            client, action="create", memory_type="factual", name="Facts"
        )
        parsed = json.loads(result)
        assert parsed["memory_id"] == "mem_fact_001"


@pytest.mark.asyncio
async def test_list_data(client):
    with respx.mock:
        respx.get("http://testserver:8080/api/v1/list").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "data_id": "data_001",
                            "name": "Report",
                            "tags": ["quarterly"],
                        },
                        {"data_id": "data_002", "name": "Notes", "tags": []},
                    ]
                },
            )
        )
        result = await tool_list_data(client, limit=10)
        assert "Report" in result
        assert "quarterly" in result
        assert "Notes" in result
