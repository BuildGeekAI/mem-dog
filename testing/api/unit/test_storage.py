"""
Unit tests for storage layer using mock storage.
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../api'))

from app.models import DataMetadata, VersionInfo


class TestMockStorageCreate:
    """Tests for creating data."""
    
    def test_create_data_returns_id_and_version(self, mock_storage):
        """Test that create_data returns valid data_id and version."""
        data_id, version = mock_storage.create_data(
            content=b'test content',
            content_type='text/plain',
            user='test-user'
        )
        
        assert data_id is not None
        assert isinstance(data_id, str) and len(data_id) >= 1  # opaque ID (UUID or data_<ulid>)
        assert version == 1
    
    def test_create_data_stores_content(self, mock_storage):
        """Test that content is stored correctly."""
        content = b'{"message": "hello"}'
        data_id, version = mock_storage.create_data(
            content=content,
            content_type='application/json',
            user='test-user'
        )
        
        stored_content, stored_type = mock_storage.get_raw_data(data_id, version)
        assert stored_content == content
        assert stored_type == 'application/json'
    
    def test_create_data_creates_metadata(self, mock_storage):
        """Test that metadata is created."""
        data_id, version = mock_storage.create_data(
            content=b'test',
            content_type='text/plain',
            user='test-user'
        )
        
        metadata = mock_storage.get_metadata(data_id)
        assert metadata.data_id == data_id
        assert metadata.current_version == 1
        assert len(metadata.versions) == 1
        assert metadata.versions[0].version == 1
        assert metadata.versions[0].content_type == 'text/plain'
        assert metadata.versions[0].size == 4  # len(b'test')
    
    def test_create_data_records_timeline(self, mock_storage):
        """Test that timeline entry is created."""
        data_id, version = mock_storage.create_data(
            content=b'test',
            content_type='text/plain',
            user='timeline-user'
        )
        
        timeline = mock_storage.get_timeline('timeline-user')
        assert len(timeline) == 1
        assert timeline[0].data_id == data_id
        assert timeline[0].version == 1
        assert timeline[0].action == 'create'


class TestMockStorageRead:
    """Tests for reading data."""
    
    def test_get_raw_data_by_version(self, mock_storage):
        """Test getting data by specific version."""
        content = b'version 1 content'
        data_id, _ = mock_storage.create_data(
            content=content,
            content_type='text/plain',
            user='test-user'
        )
        
        stored_content, content_type = mock_storage.get_raw_data(data_id, 1)
        assert stored_content == content
    
    def test_get_raw_data_current_version(self, mock_storage):
        """Test getting current version when version is None."""
        data_id, _ = mock_storage.create_data(
            content=b'v1',
            content_type='text/plain',
            user='test-user'
        )
        mock_storage.update_data(
            data_id=data_id,
            content=b'v2',
            content_type='text/plain',
            user='test-user'
        )
        
        content, _ = mock_storage.get_raw_data(data_id, version=None)
        assert content == b'v2'
    
    def test_get_raw_data_not_found(self, mock_storage):
        """Test FileNotFoundError for non-existent data."""
        with pytest.raises(FileNotFoundError):
            mock_storage.get_raw_data('non-existent-id', 1)
    
    def test_get_metadata(self, mock_storage, created_data_item):
        """Test getting metadata."""
        data_id, _ = created_data_item
        metadata = mock_storage.get_metadata(data_id)
        
        assert metadata.data_id == data_id
        assert isinstance(metadata, DataMetadata)
    
    def test_get_metadata_not_found(self, mock_storage):
        """Test FileNotFoundError for non-existent metadata."""
        with pytest.raises(FileNotFoundError):
            mock_storage.get_metadata('non-existent-id')


class TestMockStorageUpdate:
    """Tests for updating data."""
    
    def test_update_increments_version(self, mock_storage, created_data_item):
        """Test that update increments version number."""
        data_id, initial_version = created_data_item
        
        new_version = mock_storage.update_data(
            data_id=data_id,
            content=b'updated content',
            content_type='text/plain',
            user='test-user'
        )
        
        assert new_version == initial_version + 1
    
    def test_update_stores_new_content(self, mock_storage, created_data_item):
        """Test that update stores new content."""
        data_id, _ = created_data_item
        new_content = b'brand new content'
        
        new_version = mock_storage.update_data(
            data_id=data_id,
            content=new_content,
            content_type='text/plain',
            user='test-user'
        )
        
        stored_content, _ = mock_storage.get_raw_data(data_id, new_version)
        assert stored_content == new_content
    
    def test_update_preserves_old_versions(self, mock_storage, sample_json_content):
        """Test that old versions are preserved."""
        original_content = b'original'
        data_id, _ = mock_storage.create_data(
            content=original_content,
            content_type='text/plain',
            user='test-user'
        )
        
        mock_storage.update_data(
            data_id=data_id,
            content=b'updated',
            content_type='text/plain',
            user='test-user'
        )
        
        # Old version should still be accessible
        old_content, _ = mock_storage.get_raw_data(data_id, 1)
        assert old_content == original_content
    
    def test_update_adds_version_to_metadata(self, mock_storage, created_data_item):
        """Test that metadata is updated with new version."""
        data_id, _ = created_data_item
        
        mock_storage.update_data(
            data_id=data_id,
            content=b'v2',
            content_type='application/octet-stream',
            user='test-user'
        )
        
        metadata = mock_storage.get_metadata(data_id)
        assert metadata.current_version == 2
        assert len(metadata.versions) == 2
        assert metadata.versions[1].content_type == 'application/octet-stream'
    
    def test_update_records_timeline(self, mock_storage):
        """Test that update records timeline entry."""
        data_id, _ = mock_storage.create_data(
            content=b'v1',
            content_type='text/plain',
            user='timeline-test'
        )
        
        mock_storage.update_data(
            data_id=data_id,
            content=b'v2',
            content_type='text/plain',
            user='timeline-test'
        )
        
        timeline = mock_storage.get_timeline('timeline-test')
        assert len(timeline) == 2
        # Timeline is sorted descending by timestamp
        assert timeline[0].action == 'update'
        assert timeline[0].version == 2
    
    def test_update_non_existent_raises(self, mock_storage):
        """Test that updating non-existent data raises error."""
        with pytest.raises(FileNotFoundError):
            mock_storage.update_data(
                data_id='non-existent',
                content=b'content',
                content_type='text/plain',
                user='test-user'
            )


class TestMockStorageDelete:
    """Tests for deleting data."""
    
    def test_delete_removes_data(self, mock_storage, created_data_item):
        """Test that delete removes data."""
        data_id, version = created_data_item
        
        mock_storage.delete_data(data_id)
        
        with pytest.raises(FileNotFoundError):
            mock_storage.get_raw_data(data_id, version)
    
    def test_delete_removes_metadata(self, mock_storage, created_data_item):
        """Test that delete removes metadata."""
        data_id, _ = created_data_item
        
        mock_storage.delete_data(data_id)
        
        with pytest.raises(FileNotFoundError):
            mock_storage.get_metadata(data_id)
    
    def test_delete_removes_all_versions(self, mock_storage):
        """Test that delete removes all versions."""
        data_id, _ = mock_storage.create_data(
            content=b'v1',
            content_type='text/plain',
            user='test-user'
        )
        mock_storage.update_data(
            data_id=data_id,
            content=b'v2',
            content_type='text/plain',
            user='test-user'
        )
        mock_storage.update_data(
            data_id=data_id,
            content=b'v3',
            content_type='text/plain',
            user='test-user'
        )
        
        mock_storage.delete_data(data_id)
        
        for version in [1, 2, 3]:
            with pytest.raises(FileNotFoundError):
                mock_storage.get_raw_data(data_id, version)
    
    def test_delete_non_existent_is_safe(self, mock_storage):
        """Test that deleting non-existent data doesn't raise."""
        # Should not raise
        mock_storage.delete_data('non-existent-id')


class TestMockStorageList:
    """Tests for listing data."""
    
    def test_list_all_metadata_empty(self, mock_storage):
        """Test listing with no data."""
        items = mock_storage.list_all_metadata()
        assert items == []
    
    def test_list_all_metadata_returns_items(self, mock_storage):
        """Test listing returns created items."""
        mock_storage.create_data(b'data1', 'text/plain', 'user')
        mock_storage.create_data(b'data2', 'application/json', 'user')
        
        items = mock_storage.list_all_metadata()
        assert len(items) == 2
    
    def test_list_all_metadata_sorted_by_updated(self, mock_storage):
        """Test that list is sorted by updated_at descending."""
        import time
        
        id1, _ = mock_storage.create_data(b'first', 'text/plain', 'user')
        time.sleep(0.01)  # Small delay to ensure different timestamps
        id2, _ = mock_storage.create_data(b'second', 'text/plain', 'user')
        
        items = mock_storage.list_all_metadata()
        # Most recently updated should be first
        assert items[0].data_id == id2


class TestMockStorageTimeline:
    """Tests for timeline functionality."""
    
    def test_get_timeline_empty(self, mock_storage):
        """Test getting timeline for user with no entries."""
        timeline = mock_storage.get_timeline('no-activity-user')
        assert timeline == []
    
    def test_get_timeline_returns_entries(self, mock_storage):
        """Test getting timeline returns recorded entries."""
        mock_storage.create_data(b'data', 'text/plain', 'active-user')
        
        timeline = mock_storage.get_timeline('active-user')
        assert len(timeline) == 1
        assert timeline[0].user == 'active-user'
    
    def test_timeline_per_user(self, mock_storage):
        """Test that timeline is per-user."""
        mock_storage.create_data(b'data1', 'text/plain', 'user-a')
        mock_storage.create_data(b'data2', 'text/plain', 'user-b')
        mock_storage.create_data(b'data3', 'text/plain', 'user-a')
        
        timeline_a = mock_storage.get_timeline('user-a')
        timeline_b = mock_storage.get_timeline('user-b')
        
        assert len(timeline_a) == 2
        assert len(timeline_b) == 1
    
    def test_record_timeline_directly(self, mock_storage):
        """Test recording timeline entry directly."""
        mock_storage.record_timeline(
            user='direct-user',
            data_id='manual-id',
            version=5,
            action='delete'
        )
        
        timeline = mock_storage.get_timeline('direct-user')
        assert len(timeline) == 1
        assert timeline[0].data_id == 'manual-id'
        assert timeline[0].version == 5
        assert timeline[0].action == 'delete'
