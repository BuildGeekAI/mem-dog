"""
Integration tests for the data API endpoints.
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../api'))


class TestDataEndpointCreate:
    """Tests for POST /api/v1/data endpoint."""
    
    def test_create_data_with_json_content(self, test_client):
        """Test creating data with JSON content."""
        response = test_client.post(
            "/api/v1/data",
            data={"content": '{"message": "hello"}'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data_id" in data
        assert data["version"] == 1
        assert data["message"] == "Data created successfully"
    
    def test_create_data_with_file_upload(self, test_client):
        """Test creating data with file upload."""
        file_content = b"This is test file content"
        
        response = test_client.post(
            "/api/v1/data",
            files={"file": ("test.txt", file_content, "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "data_id" in data
        assert data["version"] == 1
    
    def test_create_data_without_content_fails(self, test_client):
        """Test that creating data without content fails."""
        response = test_client.post("/api/v1/data", data={})
        
        assert response.status_code == 400
        assert "Either file or content must be provided" in response.json()["detail"]
    
    def test_create_multiple_data_items(self, test_client):
        """Test creating multiple data items."""
        ids = []
        for i in range(3):
            response = test_client.post(
                "/api/v1/data",
                data={"content": f'{{"item": {i}}}'}
            )
            assert response.status_code == 200
            ids.append(response.json()["data_id"])
        
        # All IDs should be unique
        assert len(set(ids)) == 3


class TestDataEndpointList:
    """Tests for GET /api/v1/data endpoint."""
    
    def test_list_data_empty(self, test_client):
        """Test listing when no data exists (paginated response)."""
        response = test_client.get("/api/v1/data")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data and "total" in data and "skip" in data and "limit" in data
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_data_returns_items(self, test_client):
        """Test listing returns created items (paginated)."""
        test_client.post("/api/v1/data", data={"content": '{"a": 1}'})
        test_client.post("/api/v1/data", data={"content": '{"b": 2}'})
        response = test_client.get("/api/v1/data")
        assert response.status_code == 200
        data = response.json()
        items = data["items"]
        assert len(items) == 2
        assert data["total"] == 2

    def test_list_data_contains_required_fields(self, test_client):
        """Test that list items contain required fields."""
        test_client.post("/api/v1/data", data={"content": '{"test": true}'})
        response = test_client.get("/api/v1/data")
        data = response.json()
        items = data["items"]
        assert len(items) == 1
        item = items[0]
        assert "data_id" in item
        assert "current_version" in item
        assert "created_at" in item
        assert "updated_at" in item
        assert "content_type" in item
        assert "size" in item


class TestDataEndpointGet:
    """Tests for GET /api/v1/data/{data_id} endpoint."""
    
    def test_get_data_by_id(self, test_client):
        """Test getting data by ID."""
        content = '{"message": "test data"}'
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": content}
        )
        data_id = create_response.json()["data_id"]
        
        response = test_client.get(f"/api/v1/data/{data_id}")
        
        assert response.status_code == 200
        assert response.text == content
    
    def test_get_data_specific_version(self, test_client):
        """Test getting specific version of data."""
        # Create and update
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "version 1"}
        )
        data_id = create_response.json()["data_id"]
        
        test_client.put(
            f"/api/v1/data/{data_id}",
            data={"content": "version 2"}
        )
        
        # Get version 1
        response = test_client.get(f"/api/v1/data/{data_id}?version=1")
        assert response.text == "version 1"
        
        # Get version 2 (current)
        response = test_client.get(f"/api/v1/data/{data_id}?version=2")
        assert response.text == "version 2"
    
    def test_get_data_not_found(self, test_client):
        """Test 404 for non-existent data."""
        response = test_client.get("/api/v1/data/non-existent-id")
        
        assert response.status_code == 404
    
    def test_get_data_version_not_found(self, test_client):
        """Test 404 for non-existent version."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "test"}
        )
        data_id = create_response.json()["data_id"]
        
        response = test_client.get(f"/api/v1/data/{data_id}?version=999")
        
        assert response.status_code == 404


class TestDataEndpointGetMetadata:
    """Tests for GET /api/v1/data/{data_id}/metadata endpoint."""
    
    def test_get_metadata(self, test_client):
        """Test getting metadata for data item."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": '{"test": true}'}
        )
        data_id = create_response.json()["data_id"]
        
        response = test_client.get(f"/api/v1/data/{data_id}/metadata")
        
        assert response.status_code == 200
        metadata = response.json()
        assert metadata["data_id"] == data_id
        assert metadata["current_version"] == 1
        assert "versions" in metadata
        assert len(metadata["versions"]) == 1
    
    def test_get_metadata_not_found(self, test_client):
        """Test 404 for non-existent metadata."""
        response = test_client.get("/api/v1/data/non-existent/metadata")
        
        assert response.status_code == 404


class TestDataEndpointUpdate:
    """Tests for PUT /api/v1/data/{data_id} endpoint."""
    
    def test_update_data_increments_version(self, test_client):
        """Test that update increments version."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "original"}
        )
        data_id = create_response.json()["data_id"]
        
        update_response = test_client.put(
            f"/api/v1/data/{data_id}",
            data={"content": "updated"}
        )
        
        assert update_response.status_code == 200
        assert update_response.json()["version"] == 2
    
    def test_update_data_stores_new_content(self, test_client):
        """Test that update stores new content."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "original"}
        )
        data_id = create_response.json()["data_id"]
        
        test_client.put(
            f"/api/v1/data/{data_id}",
            data={"content": "updated content"}
        )
        
        get_response = test_client.get(f"/api/v1/data/{data_id}")
        assert get_response.text == "updated content"
    
    def test_update_with_file(self, test_client):
        """Test updating with file upload."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "original text"}
        )
        data_id = create_response.json()["data_id"]
        
        response = test_client.put(
            f"/api/v1/data/{data_id}",
            files={"file": ("new.txt", b"new file content", "text/plain")}
        )
        
        assert response.status_code == 200
        assert response.json()["version"] == 2
    
    def test_update_non_existent_returns_404(self, test_client):
        """Test 404 for updating non-existent data."""
        response = test_client.put(
            "/api/v1/data/non-existent",
            data={"content": "test"}
        )
        
        assert response.status_code == 404
    
    def test_update_without_content_fails(self, test_client):
        """Test that update without content fails."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "original"}
        )
        data_id = create_response.json()["data_id"]
        
        response = test_client.put(f"/api/v1/data/{data_id}", data={})
        
        assert response.status_code == 400


class TestDataEndpointDelete:
    """Tests for DELETE /api/v1/data/{data_id} endpoint."""
    
    def test_delete_data(self, test_client):
        """Test deleting data."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "to be deleted"}
        )
        data_id = create_response.json()["data_id"]
        
        delete_response = test_client.delete(f"/api/v1/data/{data_id}")
        
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Data deleted successfully"
    
    def test_delete_removes_data(self, test_client):
        """Test that deleted data is no longer accessible."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "to be deleted"}
        )
        data_id = create_response.json()["data_id"]
        
        test_client.delete(f"/api/v1/data/{data_id}")
        
        get_response = test_client.get(f"/api/v1/data/{data_id}")
        assert get_response.status_code == 404
    
    def test_delete_non_existent_returns_404(self, test_client):
        """Test 404 for deleting non-existent data."""
        response = test_client.delete("/api/v1/data/non-existent")
        
        assert response.status_code == 404


class TestDataCRUDFlow:
    """End-to-end tests for complete CRUD flows."""
    
    def test_complete_crud_flow(self, test_client):
        """Test complete create, read, update, delete flow."""
        # Create
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": '{"step": "create"}'}
        )
        assert create_response.status_code == 200
        data_id = create_response.json()["data_id"]
        
        # Read
        read_response = test_client.get(f"/api/v1/data/{data_id}")
        assert read_response.status_code == 200
        assert json.loads(read_response.text)["step"] == "create"
        
        # Update
        update_response = test_client.put(
            f"/api/v1/data/{data_id}",
            data={"content": '{"step": "update"}'}
        )
        assert update_response.status_code == 200
        assert update_response.json()["version"] == 2
        
        # Read updated
        read_response = test_client.get(f"/api/v1/data/{data_id}")
        assert json.loads(read_response.text)["step"] == "update"
        
        # Read old version
        read_v1_response = test_client.get(f"/api/v1/data/{data_id}?version=1")
        assert json.loads(read_v1_response.text)["step"] == "create"
        
        # Delete
        delete_response = test_client.delete(f"/api/v1/data/{data_id}")
        assert delete_response.status_code == 200
        
        # Verify deleted
        final_response = test_client.get(f"/api/v1/data/{data_id}")
        assert final_response.status_code == 404
