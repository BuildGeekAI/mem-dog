"""
Integration tests for the versions API endpoints.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../api'))


class TestVersionsEndpointList:
    """Tests for GET /api/v1/versions/{data_id} endpoint."""
    
    def test_get_versions_single_version(self, test_client):
        """Test getting versions for data with single version."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "test content"}
        )
        data_id = create_response.json()["data_id"]
        
        response = test_client.get(f"/api/v1/versions/{data_id}")
        
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 1
        assert versions[0]["version"] == 1
    
    def test_get_versions_multiple_versions(self, test_client):
        """Test getting versions for data with multiple versions."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "v1"}
        )
        data_id = create_response.json()["data_id"]
        
        # Create multiple updates
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "v2"})
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "v3"})
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "v4"})
        
        response = test_client.get(f"/api/v1/versions/{data_id}")
        
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 4
        
        # Check versions are in order
        for i, version in enumerate(versions, start=1):
            assert version["version"] == i
    
    def test_get_versions_contains_required_fields(self, test_client):
        """Test that version entries contain required fields."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": '{"test": true}'}
        )
        data_id = create_response.json()["data_id"]
        
        response = test_client.get(f"/api/v1/versions/{data_id}")
        versions = response.json()
        
        assert len(versions) == 1
        version = versions[0]
        assert "version" in version
        assert "timestamp" in version
        assert "size" in version
        assert "content_type" in version
    
    def test_get_versions_not_found(self, test_client):
        """Test 404 for non-existent data."""
        response = test_client.get("/api/v1/versions/non-existent-id")
        
        assert response.status_code == 404
    
    def test_versions_track_content_type_changes(self, test_client):
        """Test that version tracks content type changes."""
        # Create with text content
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "text content"}
        )
        data_id = create_response.json()["data_id"]
        
        # Update with file (different content type)
        test_client.put(
            f"/api/v1/data/{data_id}",
            files={"file": ("data.bin", b"\x00\x01\x02", "application/octet-stream")}
        )
        
        response = test_client.get(f"/api/v1/versions/{data_id}")
        versions = response.json()
        
        assert len(versions) == 2
        assert versions[0]["content_type"] == "application/json"  # JSON content default
        assert versions[1]["content_type"] == "application/octet-stream"


class TestVersionsEndpointGetSpecific:
    """Tests for GET /api/v1/versions/{data_id}/{version} endpoint."""
    
    def test_get_specific_version(self, test_client):
        """Test getting specific version content."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "version 1 content"}
        )
        data_id = create_response.json()["data_id"]
        
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "version 2 content"})
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "version 3 content"})
        
        # Get each version
        v1_response = test_client.get(f"/api/v1/versions/{data_id}/1")
        assert v1_response.status_code == 200
        assert v1_response.text == "version 1 content"
        
        v2_response = test_client.get(f"/api/v1/versions/{data_id}/2")
        assert v2_response.status_code == 200
        assert v2_response.text == "version 2 content"
        
        v3_response = test_client.get(f"/api/v1/versions/{data_id}/3")
        assert v3_response.status_code == 200
        assert v3_response.text == "version 3 content"
    
    def test_get_specific_version_not_found(self, test_client):
        """Test 404 for non-existent version."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "test"}
        )
        data_id = create_response.json()["data_id"]
        
        response = test_client.get(f"/api/v1/versions/{data_id}/99")
        
        assert response.status_code == 404
    
    def test_get_specific_version_data_not_found(self, test_client):
        """Test 404 for non-existent data ID."""
        response = test_client.get("/api/v1/versions/non-existent/1")
        
        assert response.status_code == 404
    
    def test_get_specific_version_preserves_content_type(self, test_client):
        """Test that content type is preserved per version."""
        # Create with JSON content
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": '{"json": true}'}
        )
        data_id = create_response.json()["data_id"]
        
        # Update with plain text file
        test_client.put(
            f"/api/v1/data/{data_id}",
            files={"file": ("test.txt", b"plain text", "text/plain")}
        )
        
        # Version 1 should have JSON content type
        v1_response = test_client.get(f"/api/v1/versions/{data_id}/1")
        assert "application/json" in v1_response.headers.get("content-type", "")
        
        # Version 2 should have text/plain content type
        v2_response = test_client.get(f"/api/v1/versions/{data_id}/2")
        assert "text/plain" in v2_response.headers.get("content-type", "")


class TestVersionsFlow:
    """End-to-end tests for versioning flows."""
    
    def test_version_history_integrity(self, test_client):
        """Test that version history maintains integrity through updates."""
        contents = [
            "Initial content",
            "First update",
            "Second update",
            "Third update",
            "Final content"
        ]
        
        # Create initial
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": contents[0]}
        )
        data_id = create_response.json()["data_id"]
        
        # Make updates
        for content in contents[1:]:
            test_client.put(f"/api/v1/data/{data_id}", data={"content": content})
        
        # Verify all versions are retrievable and correct
        for i, expected_content in enumerate(contents, start=1):
            response = test_client.get(f"/api/v1/versions/{data_id}/{i}")
            assert response.status_code == 200
            assert response.text == expected_content
        
        # Verify version list
        versions_response = test_client.get(f"/api/v1/versions/{data_id}")
        versions = versions_response.json()
        assert len(versions) == 5
    
    def test_versions_independent_of_current(self, test_client):
        """Test that accessing old versions doesn't affect current."""
        create_response = test_client.post(
            "/api/v1/data",
            data={"content": "original"}
        )
        data_id = create_response.json()["data_id"]
        
        test_client.put(f"/api/v1/data/{data_id}", data={"content": "updated"})
        
        # Access old version
        test_client.get(f"/api/v1/versions/{data_id}/1")
        
        # Current should still be v2
        current_response = test_client.get(f"/api/v1/data/{data_id}")
        assert current_response.text == "updated"
        
        # Metadata should still show current as v2
        meta_response = test_client.get(f"/api/v1/data/{data_id}/metadata")
        assert meta_response.json()["current_version"] == 2
