"""
Integration tests for the memories API endpoints.

Tests the /api/v1/memories endpoint (replaces the former /api/v1/timeline).
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../api'))


class TestMemoriesListEndpoint:
    """Tests for GET /api/v1/memories endpoint."""

    def test_get_memories_empty(self, test_client):
        """Test getting memories when none exist."""
        response = test_client.get("/api/v1/memories")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert data["items"] == []
        assert data["total"] == 0
        assert data["skip"] == 0
        assert data["limit"] == 100

    def test_get_memories_after_create(self, test_client):
        """Test memories list returns created memory."""
        test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "timeline",
                "name": "Test Timeline",
                "user_id": "demo",
            },
        )

        response = test_client.get("/api/v1/memories")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["memory_type"] == "timeline"
        assert data["items"][0]["name"] == "Test Timeline"
        assert data["items"][0]["user_id"] == "demo"

    def test_memories_contain_required_fields(self, test_client):
        """Test memory items contain required fields."""
        test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "user",
                "name": "User Memory",
                "user_id": "demo",
            },
        )

        response = test_client.get("/api/v1/memories")
        items = response.json()["items"]

        assert len(items) == 1
        entry = items[0]
        assert "memory_id" in entry
        assert "memory_type" in entry
        assert "duration" in entry
        assert "name" in entry
        assert "user_id" in entry
        assert "data_count" in entry
        assert "data_ids" in entry
        assert "metadata" in entry
        assert "created_at" in entry
        assert "updated_at" in entry

    def test_memories_filter_by_user_id(self, test_client):
        """Test memories can be filtered by user_id."""
        test_client.post(
            "/api/v1/memories",
            json={"memory_type": "timeline", "name": "Demo Timeline", "user_id": "demo"},
        )
        test_client.post(
            "/api/v1/memories",
            json={"memory_type": "timeline", "name": "Other Timeline", "user_id": "other-user"},
        )

        response = test_client.get("/api/v1/memories?user_id=demo")
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["user_id"] == "demo"

    def test_memories_filter_by_memory_type(self, test_client):
        """Test memories can be filtered by memory_type."""
        test_client.post(
            "/api/v1/memories",
            json={"memory_type": "timeline", "name": "Timeline", "user_id": "demo"},
        )
        test_client.post(
            "/api/v1/memories",
            json={"memory_type": "session", "name": "Session", "user_id": "demo"},
        )

        response = test_client.get("/api/v1/memories?memory_type=timeline")
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["memory_type"] == "timeline"

    def test_memories_filter_by_duration(self, test_client):
        """Test memories can be filtered by duration."""
        test_client.post(
            "/api/v1/memories",
            json={"memory_type": "timeline", "name": "Short", "user_id": "demo"},
        )
        test_client.post(
            "/api/v1/memories",
            json={"memory_type": "user", "name": "Long", "user_id": "demo"},
        )

        response = test_client.get("/api/v1/memories?duration=short_term")
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["duration"] == "short_term"

    def test_memories_pagination(self, test_client):
        """Test memories support skip and limit."""
        for i in range(5):
            test_client.post(
                "/api/v1/memories",
                json={
                    "memory_type": "timeline",
                    "name": f"Memory {i}",
                    "user_id": "demo",
                },
            )

        response = test_client.get("/api/v1/memories?skip=2&limit=2")
        data = response.json()

        assert data["total"] == 5
        assert data["skip"] == 2
        assert data["limit"] == 2
        assert len(data["items"]) == 2


class TestMemoriesCreateEndpoint:
    """Tests for POST /api/v1/memories endpoint."""

    def test_create_memory_minimal(self, test_client):
        """Test creating a memory with required fields only."""
        response = test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "timeline",
                "name": "My Timeline",
                "user_id": "demo",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "memory_id" in data
        assert data["memory_type"] == "timeline"
        assert data["name"] == "My Timeline"
        assert data["user_id"] == "demo"
        assert data["data_count"] == 0
        assert data["data_ids"] == []

    def test_create_memory_with_description_and_metadata(self, test_client):
        """Test creating a memory with optional description and metadata."""
        response = test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "user",
                "name": "User Memory",
                "user_id": "demo",
                "description": "A long-term user memory",
                "metadata": {"key": "value"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "A long-term user memory"
        assert data["metadata"] == {"key": "value"}

    def test_create_memory_session_type(self, test_client):
        """Test creating a session-type memory."""
        response = test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "session",
                "name": "Active Session",
                "user_id": "demo",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["memory_type"] == "session"
        assert data["active"] is True


class TestMemoriesEntriesEndpoint:
    """Tests for GET /api/v1/memories/{id}/entries endpoint."""

    def test_get_entries_empty_memory(self, test_client):
        """Test getting entries for a memory with no data."""
        create_resp = test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "timeline",
                "name": "Empty Timeline",
                "user_id": "demo",
            },
        )
        memory_id = create_resp.json()["memory_id"]

        response = test_client.get(f"/api/v1/memories/{memory_id}/entries")

        assert response.status_code == 200
        data = response.json()
        assert data["memory_id"] == memory_id
        assert data["entries"] == []
        assert data["total"] == 0

    def test_get_entries_after_adding_data(self, test_client):
        """Test entries endpoint returns data associations."""
        create_resp = test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "timeline",
                "name": "Timeline",
                "user_id": "demo",
            },
        )
        memory_id = create_resp.json()["memory_id"]

        # Create data and add to memory
        data_resp = test_client.post("/api/v1/data", data={"content": '{"test": 1}'})
        data_id = data_resp.json()["data_id"]
        test_client.post(
            f"/api/v1/memories/{memory_id}/data",
            json={"data_ids": [data_id]},
        )

        response = test_client.get(f"/api/v1/memories/{memory_id}/entries")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["entries"]) == 1
        assert data["entries"][0]["data_id"] == data_id
        assert data["entries"][0]["memory_id"] == memory_id

    def test_get_entries_404_for_unknown_memory(self, test_client):
        """Test entries returns 404 for non-existent memory."""
        response = test_client.get("/api/v1/memories/non-existent-id/entries")

        assert response.status_code == 404


class TestMemoriesFlow:
    """End-to-end tests for memory operations."""

    def test_create_list_get_flow(self, test_client):
        """Test create, list, and get flow."""
        create_resp = test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "timeline",
                "name": "Flow Test",
                "user_id": "demo",
            },
        )
        memory_id = create_resp.json()["memory_id"]

        list_resp = test_client.get("/api/v1/memories")
        assert any(m["memory_id"] == memory_id for m in list_resp.json()["items"])

        get_resp = test_client.get(f"/api/v1/memories/{memory_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["memory_id"] == memory_id
        assert get_resp.json()["name"] == "Flow Test"

    def test_memory_with_multiple_data_items(self, test_client):
        """Test memory tracks multiple data items correctly."""
        create_resp = test_client.post(
            "/api/v1/memories",
            json={
                "memory_type": "timeline",
                "name": "Multi-Data",
                "user_id": "demo",
            },
        )
        memory_id = create_resp.json()["memory_id"]

        data_ids = []
        for i in range(3):
            data_resp = test_client.post(
                "/api/v1/data",
                data={"content": f'{{"item": {i}}}'},
            )
            data_ids.append(data_resp.json()["data_id"])

        test_client.post(
            f"/api/v1/memories/{memory_id}/data",
            json={"data_ids": data_ids},
        )

        entries_resp = test_client.get(f"/api/v1/memories/{memory_id}/entries")
        entries = entries_resp.json()["entries"]

        assert len(entries) == 3
        entry_data_ids = [e["data_id"] for e in entries]
        for did in data_ids:
            assert did in entry_data_ids


class TestHealthAndRoot:
    """Tests for health and root endpoints."""

    def test_root_endpoint(self, test_client):
        """Test root endpoint returns service info."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "mem-dog-api"
        assert "version" in data

    def test_health_endpoint(self, test_client):
        """Test health endpoint returns healthy status."""
        response = test_client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
