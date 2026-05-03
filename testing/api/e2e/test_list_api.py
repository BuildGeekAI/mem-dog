"""
Integration tests for the list API endpoints.
"""
import pytest
import json
import base64
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../api'))


class TestListEndpointBasic:
    """Tests for GET /api/v1/list endpoint - basic functionality."""
    
    def test_list_empty_user_data(self, test_client):
        """Test getting list when user has no data."""
        response = test_client.get("/api/v1/list")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"] == "demo"
        assert data["count"] == 0
        assert data["items"] == []
        # Check pagination info
        assert "pagination" in data
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["has_more"] == False
    
    def test_list_default_format_is_timeline(self, test_client):
        """Test that default format is timeline."""
        test_client.post("/api/v1/data", data={"content": "test"})
        
        response = test_client.get("/api/v1/list")
        
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "timeline"
    
    def test_list_with_user_parameter(self, test_client):
        """Test list with specific user parameter."""
        # Create data (goes to default user 'demo')
        test_client.post("/api/v1/data", data={"content": "test"})
        
        # Query for different user should be empty
        response = test_client.get("/api/v1/list?user=other-user")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"] == "other-user"
        assert data["count"] == 0
    
    def test_list_returns_pagination_info(self, test_client):
        """Test that list response includes pagination info."""
        test_client.post("/api/v1/data", data={"content": "test"})
        
        response = test_client.get("/api/v1/list")
        data = response.json()
        
        assert "pagination" in data
        pagination = data["pagination"]
        assert "total" in pagination
        assert "limit" in pagination
        assert "offset" in pagination
        assert "has_more" in pagination


class TestListTimelineFormat:
    """Tests for GET /api/v1/list?format=timeline."""
    
    def test_list_timeline_format(self, test_client):
        """Test list with timeline format."""
        test_client.post("/api/v1/data", data={"content": "test data"})
        
        response = test_client.get("/api/v1/list?format=timeline")
        
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "timeline"
        assert data["count"] == 1
        assert len(data["items"]) == 1
    
    def test_timeline_format_contains_action_info(self, test_client):
        """Test that timeline format contains action information."""
        test_client.post("/api/v1/data", data={"content": "test"})
        
        response = test_client.get("/api/v1/list?format=timeline")
        items = response.json()["items"]
        
        assert len(items) == 1
        item = items[0]
        assert "action" in item
        assert item["action"] == "create"
        assert "timestamp" in item
        assert "data_id" in item
        assert "version" in item
    
    def test_timeline_format_tracks_updates(self, test_client):
        """Test that timeline format tracks create and update actions."""
        create_response = test_client.post("/api/v1/data", data={"content": "original"})
        data_id = create_response.json()["data_id"]
        
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "updated"})
        
        response = test_client.get("/api/v1/list?format=timeline")
        data = response.json()
        
        assert data["count"] == 2
        # Should be sorted by timestamp descending (newest first)
        assert data["items"][0]["action"] == "update"
        assert data["items"][1]["action"] == "create"
    
    def test_timeline_format_includes_detail_fields(self, test_client):
        """Test that timeline format includes content_type and size."""
        test_client.post("/api/v1/data", data={"content": '{"test": true}'})
        
        response = test_client.get("/api/v1/list?format=timeline")
        items = response.json()["items"]
        
        item = items[0]
        assert "content_type" in item
        assert "size" in item


class TestListMetaFormat:
    """Tests for GET /api/v1/list?format=meta."""
    
    def test_list_meta_format(self, test_client):
        """Test list with meta format."""
        test_client.post("/api/v1/data", data={"content": "test data"})
        
        response = test_client.get("/api/v1/list?format=meta")
        
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "meta"
        assert data["count"] == 1
    
    def test_meta_format_contains_metadata_fields(self, test_client):
        """Test that meta format contains all metadata fields."""
        test_client.post("/api/v1/data", data={"content": '{"test": true}'})
        
        response = test_client.get("/api/v1/list?format=meta")
        items = response.json()["items"]
        
        assert len(items) == 1
        item = items[0]
        assert "data_id" in item
        assert "current_version" in item
        assert "created_at" in item
        assert "updated_at" in item
        assert "content_type" in item
        assert "size" in item
        assert "last_action" in item
        assert "last_action_timestamp" in item
    
    def test_meta_format_shows_latest_version(self, test_client):
        """Test that meta format shows the latest version info."""
        create_response = test_client.post("/api/v1/data", data={"content": "v1"})
        data_id = create_response.json()["data_id"]
        
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "version 2 content"})
        
        response = test_client.get("/api/v1/list?format=meta")
        items = response.json()["items"]
        
        assert len(items) == 1
        assert items[0]["current_version"] == 2
    
    def test_meta_format_includes_last_action(self, test_client):
        """Test that meta format includes last action info."""
        create_response = test_client.post("/api/v1/data", data={"content": "test"})
        data_id = create_response.json()["data_id"]
        
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "updated"})
        
        response = test_client.get("/api/v1/list?format=meta")
        items = response.json()["items"]
        
        assert items[0]["last_action"] == "update"
        assert items[0]["last_action_timestamp"] is not None
    
    def test_meta_format_sorted_by_updated_at(self, test_client):
        """Test that meta format is sorted by updated_at descending."""
        import time
        
        # Create multiple items
        for i in range(3):
            test_client.post("/api/v1/data", data={"content": f"item {i}"})
            time.sleep(0.01)
        
        response = test_client.get("/api/v1/list?format=meta")
        items = response.json()["items"]
        
        # Should be sorted by updated_at descending
        updated_times = [item["updated_at"] for item in items]
        assert updated_times == sorted(updated_times, reverse=True)


class TestListRawFormat:
    """Tests for GET /api/v1/list?format=raw."""
    
    def test_list_raw_format(self, test_client):
        """Test list with raw format."""
        test_client.post("/api/v1/data", data={"content": "test data"})
        
        response = test_client.get("/api/v1/list?format=raw")
        
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "raw"
        assert data["count"] == 1
    
    def test_raw_format_contains_content(self, test_client):
        """Test that raw format contains actual content."""
        original_content = '{"message": "hello world"}'
        test_client.post("/api/v1/data", data={"content": original_content})
        
        response = test_client.get("/api/v1/list?format=raw")
        items = response.json()["items"]
        
        assert len(items) == 1
        item = items[0]
        assert "content" in item
        assert "encoding" in item
        assert "content_type" in item
        assert "size" in item
    
    def test_raw_format_json_content(self, test_client):
        """Test raw format with JSON content is parsed."""
        original = {"key": "value", "number": 42}
        test_client.post("/api/v1/data", data={"content": json.dumps(original)})
        
        response = test_client.get("/api/v1/list?format=raw")
        items = response.json()["items"]
        
        # JSON content should be parsed
        assert items[0]["encoding"] == "utf-8"
        assert items[0]["content"] == original
    
    def test_raw_format_text_content(self, test_client):
        """Test raw format with text content."""
        test_client.post(
            "/api/v1/data",
            files={"file": ("test.txt", b"plain text content", "text/plain")}
        )
        
        response = test_client.get("/api/v1/list?format=raw")
        items = response.json()["items"]
        
        assert items[0]["encoding"] == "utf-8"
        assert items[0]["content"] == "plain text content"
    
    def test_raw_format_binary_content_base64(self, test_client):
        """Test raw format encodes binary content as base64."""
        binary_content = b'\x89PNG\r\n\x1a\n\x00\x00'
        test_client.post(
            "/api/v1/data",
            files={"file": ("image.png", binary_content, "image/png")}
        )
        
        response = test_client.get("/api/v1/list?format=raw")
        items = response.json()["items"]
        
        assert items[0]["encoding"] == "base64"
        # Verify we can decode it back
        decoded = base64.b64decode(items[0]["content"])
        assert decoded == binary_content
    
    def test_raw_format_excludes_deleted_items(self, test_client):
        """Test that raw format excludes deleted items."""
        # Create and then delete an item
        create_response = test_client.post("/api/v1/data", data={"content": "to delete"})
        data_id = create_response.json()["data_id"]
        test_client.delete(f"/api/v1/data/{data_id}")
        
        # Create another item that should remain
        test_client.post("/api/v1/data", data={"content": "keep this"})
        
        response = test_client.get("/api/v1/list?format=raw")
        data = response.json()
        
        # Should only have the non-deleted item
        assert data["count"] == 1
        assert data["items"][0]["content"] == "keep this"


class TestListSpecificItem:
    """Tests for GET /api/v1/list/{data_id} endpoint."""
    
    def test_get_specific_item_timeline(self, test_client):
        """Test getting specific item in timeline format."""
        create_response = test_client.post("/api/v1/data", data={"content": "test"})
        data_id = create_response.json()["data_id"]
        
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "updated"})
        
        response = test_client.get(f"/api/v1/list/{data_id}?format=timeline")
        
        assert response.status_code == 200
        data = response.json()
        assert data["data_id"] == data_id
        assert data["format"] == "timeline"
        assert len(data["entries"]) == 2
    
    def test_get_specific_item_meta(self, test_client):
        """Test getting specific item in meta format."""
        create_response = test_client.post("/api/v1/data", data={"content": "test"})
        data_id = create_response.json()["data_id"]
        
        response = test_client.get(f"/api/v1/list/{data_id}?format=meta")
        
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "meta"
        assert "metadata" in data
        assert data["metadata"]["data_id"] == data_id
    
    def test_get_specific_item_raw(self, test_client):
        """Test getting specific item in raw format."""
        original_content = '{"test": true}'
        create_response = test_client.post("/api/v1/data", data={"content": original_content})
        data_id = create_response.json()["data_id"]
        
        response = test_client.get(f"/api/v1/list/{data_id}?format=raw")
        
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "raw"
        assert "content" in data
        assert data["content"] == {"test": True}
    
    def test_get_item_not_found_for_user(self, test_client):
        """Test 404 when item doesn't belong to user."""
        create_response = test_client.post("/api/v1/data", data={"content": "test"})
        data_id = create_response.json()["data_id"]
        
        # Try to get with different user
        response = test_client.get(f"/api/v1/list/{data_id}?user=other-user")
        
        assert response.status_code == 404
    
    def test_get_item_not_found(self, test_client):
        """Test 404 for non-existent item."""
        response = test_client.get("/api/v1/list/non-existent-id")
        
        assert response.status_code == 404


class TestListMultipleItems:
    """Tests for listing multiple data items."""
    
    def test_list_multiple_items_meta(self, test_client):
        """Test listing multiple items in meta format."""
        ids = []
        for i in range(3):
            response = test_client.post("/api/v1/data", data={"content": f"item {i}"})
            ids.append(response.json()["data_id"])
        
        response = test_client.get("/api/v1/list?format=meta")
        data = response.json()
        
        assert data["count"] == 3
        returned_ids = [item["data_id"] for item in data["items"]]
        for data_id in ids:
            assert data_id in returned_ids
    
    def test_list_multiple_items_raw(self, test_client):
        """Test listing multiple items in raw format."""
        for i in range(3):
            test_client.post("/api/v1/data", data={"content": f"content {i}"})
        
        response = test_client.get("/api/v1/list?format=raw")
        data = response.json()
        
        assert data["count"] == 3
        contents = [item["content"] for item in data["items"]]
        for i in range(3):
            assert f"content {i}" in contents
    
    def test_list_with_mixed_operations(self, test_client):
        """Test list after mixed create/update/delete operations."""
        import time
        
        # Create first item
        resp1 = test_client.post("/api/v1/data", data={"content": "item 1"})
        id1 = resp1.json()["data_id"]
        time.sleep(0.01)
        
        # Create and delete second item
        resp2 = test_client.post("/api/v1/data", data={"content": "item 2"})
        id2 = resp2.json()["data_id"]
        test_client.delete(f"/api/v1/data/{id2}")
        time.sleep(0.01)
        
        # Create and update third item
        resp3 = test_client.post("/api/v1/data", data={"content": "item 3"})
        id3 = resp3.json()["data_id"]
        test_client.put(f"/api/v1/data/{id3}", data={"content": "item 3 updated"})
        
        # Check meta format (should show 2 items - deleted one excluded in meta if actually deleted)
        response = test_client.get("/api/v1/list?format=meta")
        data = response.json()
        
        # Both remaining items should be present
        assert data["count"] == 2
        
        # Check timeline format (should show all operations)
        response = test_client.get("/api/v1/list?format=timeline")
        data = response.json()
        
        # Should have: create, create, delete, create, update = 5 entries
        assert data["count"] == 5


class TestListPagination:
    """Tests for pagination functionality."""
    
    def test_pagination_default_limit(self, test_client):
        """Test that default limit is 20."""
        # Create 5 items (less than default limit)
        for i in range(5):
            test_client.post("/api/v1/data", data={"content": f"item {i}"})
        
        response = test_client.get("/api/v1/list?format=meta")
        data = response.json()
        
        assert data["pagination"]["limit"] == 20
        assert data["pagination"]["offset"] == 0
        assert data["count"] == 5
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["has_more"] == False
    
    def test_pagination_with_limit(self, test_client):
        """Test pagination with custom limit."""
        # Create 5 items
        for i in range(5):
            test_client.post("/api/v1/data", data={"content": f"item {i}"})
        
        response = test_client.get("/api/v1/list?format=meta&limit=2")
        data = response.json()
        
        assert data["count"] == 2
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["has_more"] == True
    
    def test_pagination_with_offset(self, test_client):
        """Test pagination with offset."""
        # Create 5 items
        for i in range(5):
            test_client.post("/api/v1/data", data={"content": f"item {i}"})
        
        response = test_client.get("/api/v1/list?format=meta&limit=2&offset=2")
        data = response.json()
        
        assert data["count"] == 2
        assert data["pagination"]["offset"] == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["has_more"] == True
    
    def test_pagination_last_page(self, test_client):
        """Test pagination on last page."""
        # Create 5 items
        for i in range(5):
            test_client.post("/api/v1/data", data={"content": f"item {i}"})
        
        response = test_client.get("/api/v1/list?format=meta&limit=2&offset=4")
        data = response.json()
        
        assert data["count"] == 1  # Only 1 item left
        assert data["pagination"]["offset"] == 4
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["has_more"] == False
    
    def test_pagination_beyond_total(self, test_client):
        """Test pagination with offset beyond total items."""
        # Create 3 items
        for i in range(3):
            test_client.post("/api/v1/data", data={"content": f"item {i}"})
        
        response = test_client.get("/api/v1/list?format=meta&offset=10")
        data = response.json()
        
        assert data["count"] == 0
        assert data["items"] == []
        assert data["pagination"]["total"] == 3
        assert data["pagination"]["has_more"] == False
    
    def test_pagination_timeline_format(self, test_client):
        """Test pagination with timeline format."""
        # Create items with updates to generate multiple timeline entries
        for i in range(3):
            resp = test_client.post("/api/v1/data", data={"content": f"item {i}"})
            data_id = resp.json()["data_id"]
            test_client.put(f"/api/v1/data/{data_id}", data={"content": f"item {i} updated"})
        
        # Should have 6 timeline entries (3 creates + 3 updates)
        response = test_client.get("/api/v1/list?format=timeline&limit=4")
        data = response.json()
        
        assert data["count"] == 4
        assert data["pagination"]["total"] == 6
        assert data["pagination"]["has_more"] == True
    
    def test_pagination_raw_format(self, test_client):
        """Test pagination with raw format."""
        for i in range(5):
            test_client.post("/api/v1/data", data={"content": f"item {i}"})
        
        response = test_client.get("/api/v1/list?format=raw&limit=3")
        data = response.json()
        
        assert data["count"] == 3
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["has_more"] == True
    
    def test_pagination_limit_validation_min(self, test_client):
        """Test that limit has minimum of 1."""
        response = test_client.get("/api/v1/list?limit=0")
        
        assert response.status_code == 422  # Validation error
    
    def test_pagination_limit_validation_max(self, test_client):
        """Test that limit has maximum of 100."""
        response = test_client.get("/api/v1/list?limit=101")
        
        assert response.status_code == 422  # Validation error
    
    def test_pagination_offset_validation(self, test_client):
        """Test that offset cannot be negative."""
        response = test_client.get("/api/v1/list?offset=-1")
        
        assert response.status_code == 422  # Validation error
    
    def test_pagination_preserves_sort_order(self, test_client):
        """Test that pagination preserves sort order across pages."""
        import time
        
        # Create items with small delays to ensure different timestamps
        ids = []
        for i in range(5):
            resp = test_client.post("/api/v1/data", data={"content": f"item {i}"})
            ids.append(resp.json()["data_id"])
            time.sleep(0.01)
        
        # Get first page
        response1 = test_client.get("/api/v1/list?format=meta&limit=2&offset=0")
        page1 = response1.json()["items"]
        
        # Get second page
        response2 = test_client.get("/api/v1/list?format=meta&limit=2&offset=2")
        page2 = response2.json()["items"]
        
        # Get third page
        response3 = test_client.get("/api/v1/list?format=meta&limit=2&offset=4")
        page3 = response3.json()["items"]
        
        # Combine all items
        all_items = page1 + page2 + page3
        
        # Should be sorted by updated_at descending
        updated_times = [item["updated_at"] for item in all_items]
        assert updated_times == sorted(updated_times, reverse=True)
