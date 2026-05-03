"""
Unit tests for Pydantic models.
"""
import pytest
from pydantic import ValidationError
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../api'))

from app.models import (
    VersionInfo,
    DataMetadata,
    DataListItem,
    TimelineEntry,
    TimelineEntryDetail,
    CreateDataRequest,
    CreateDataResponse,
    UpdateDataResponse,
    ErrorResponse,
)


class TestVersionInfo:
    """Tests for VersionInfo model."""
    
    def test_create_valid_version_info(self):
        """Test creating a valid VersionInfo."""
        version_info = VersionInfo(
            version=1,
            timestamp="2024-01-15T10:30:00Z",
            size=1024,
            content_type="application/json"
        )
        
        assert version_info.version == 1
        assert version_info.timestamp == "2024-01-15T10:30:00Z"
        assert version_info.size == 1024
        assert version_info.content_type == "application/json"
    
    def test_version_info_requires_all_fields(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            VersionInfo(version=1)
    
    def test_version_info_model_dump(self):
        """Test serialization to dict."""
        version_info = VersionInfo(
            version=2,
            timestamp="2024-01-16T14:00:00Z",
            size=512,
            content_type="text/plain"
        )
        
        data = version_info.model_dump()
        assert data == {
            "version": 2,
            "timestamp": "2024-01-16T14:00:00Z",
            "size": 512,
            "content_type": "text/plain"
        }


class TestDataMetadata:
    """Tests for DataMetadata model."""
    
    def test_create_valid_metadata(self):
        """Test creating valid DataMetadata."""
        metadata = DataMetadata(
            data_id="abc123",
            current_version=2,
            versions=[
                VersionInfo(
                    version=1,
                    timestamp="2024-01-15T10:30:00Z",
                    size=100,
                    content_type="application/json"
                ),
                VersionInfo(
                    version=2,
                    timestamp="2024-01-16T14:00:00Z",
                    size=150,
                    content_type="application/json"
                )
            ],
            created_at="2024-01-15T10:30:00Z",
            updated_at="2024-01-16T14:00:00Z"
        )
        
        assert metadata.data_id == "abc123"
        assert metadata.current_version == 2
        assert len(metadata.versions) == 2
        assert metadata.versions[0].version == 1
        assert metadata.versions[1].version == 2
    
    def test_metadata_with_empty_versions(self):
        """Test metadata with no versions."""
        metadata = DataMetadata(
            data_id="empty123",
            current_version=0,
            versions=[],
            created_at="2024-01-15T10:30:00Z",
            updated_at="2024-01-15T10:30:00Z"
        )
        
        assert len(metadata.versions) == 0
    
    def test_metadata_requires_data_id(self):
        """Test that data_id is required."""
        with pytest.raises(ValidationError):
            DataMetadata(
                current_version=1,
                versions=[],
                created_at="2024-01-15T10:30:00Z",
                updated_at="2024-01-15T10:30:00Z"
            )


class TestDataListItem:
    """Tests for DataListItem model."""
    
    def test_create_valid_list_item(self):
        """Test creating a valid DataListItem."""
        item = DataListItem(
            data_id="test-id",
            current_version=3,
            created_at="2024-01-10T08:00:00Z",
            updated_at="2024-01-15T12:00:00Z",
            content_type="image/png",
            size=2048
        )
        
        assert item.data_id == "test-id"
        assert item.current_version == 3
        assert item.content_type == "image/png"
        assert item.size == 2048
    
    def test_list_item_model_dump(self):
        """Test serialization to dict."""
        item = DataListItem(
            data_id="item-1",
            current_version=1,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            content_type="text/plain",
            size=100
        )
        
        data = item.model_dump()
        assert "data_id" in data
        assert "current_version" in data
        assert "content_type" in data
        assert "size" in data


class TestTimelineEntry:
    """Tests for TimelineEntry model."""
    
    def test_create_valid_timeline_entry(self):
        """Test creating a valid TimelineEntry."""
        entry = TimelineEntry(
            user="test-user",
            data_id="data-123",
            version=1,
            action="create",
            timestamp=1705315800
        )
        
        assert entry.user == "test-user"
        assert entry.data_id == "data-123"
        assert entry.version == 1
        assert entry.action == "create"
        assert entry.timestamp == 1705315800
    
    def test_timeline_entry_actions(self):
        """Test different action types."""
        for action in ["create", "update", "delete"]:
            entry = TimelineEntry(
                user="user",
                data_id="data",
                version=1,
                action=action,
                timestamp=1705315800
            )
            assert entry.action == action


class TestTimelineEntryDetail:
    """Tests for TimelineEntryDetail model."""
    
    def test_create_with_optional_fields(self):
        """Test creating with optional content_type and size."""
        detail = TimelineEntryDetail(
            user="test-user",
            data_id="data-123",
            version=1,
            action="create",
            timestamp=1705315800,
            content_type="application/json",
            size=256
        )
        
        assert detail.content_type == "application/json"
        assert detail.size == 256
    
    def test_create_without_optional_fields(self):
        """Test creating without optional fields."""
        detail = TimelineEntryDetail(
            user="test-user",
            data_id="data-123",
            version=1,
            action="create",
            timestamp=1705315800
        )
        
        assert detail.content_type is None
        assert detail.size is None


class TestCreateDataResponse:
    """Tests for CreateDataResponse model."""
    
    def test_create_valid_response(self):
        """Test creating a valid response."""
        response = CreateDataResponse(
            data_id="new-data-id",
            version=1,
            message="Data created successfully"
        )
        
        assert response.data_id == "new-data-id"
        assert response.version == 1
        assert response.message == "Data created successfully"


class TestUpdateDataResponse:
    """Tests for UpdateDataResponse model."""
    
    def test_create_valid_response(self):
        """Test creating a valid response."""
        response = UpdateDataResponse(
            data_id="existing-data-id",
            version=5,
            message="Data updated successfully"
        )
        
        assert response.data_id == "existing-data-id"
        assert response.version == 5
        assert response.message == "Data updated successfully"


class TestErrorResponse:
    """Tests for ErrorResponse model."""
    
    def test_create_with_detail(self):
        """Test creating with detail."""
        error = ErrorResponse(
            error="Not Found",
            detail="Data with id 'xyz' not found"
        )
        
        assert error.error == "Not Found"
        assert error.detail == "Data with id 'xyz' not found"
    
    def test_create_without_detail(self):
        """Test creating without optional detail."""
        error = ErrorResponse(error="Internal Server Error")
        
        assert error.error == "Internal Server Error"
        assert error.detail is None
