"""
Pytest fixtures and configuration for API testing.
"""
import pytest
import sys
import os
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import uuid
import json

# Add API directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../api'))

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.models import (
    DataMetadata,
    VersionInfo,
    DataListItem,
    TimelineEntry,
    Memory,
    MemoryCreate,
    MemoryUpdate,
    MemoryDataEntry,
    MemoryType,
    MemoryDuration,
    MEMORY_TYPE_DURATION,
)


class MockStorage:
    """
    In-memory mock storage for testing without GCS dependencies.
    Implements the same interface as BaseStorage (used by LocalStorage/GCSStorage).
    """
    
    def __init__(self):
        self.raw_data: Dict[str, Dict[int, Tuple[bytes, str]]] = {}  # data_id -> version -> (content, content_type)
        self.metadata: Dict[str, DataMetadata] = {}  # data_id -> metadata
        self.timeline: Dict[str, List[TimelineEntry]] = {}  # user -> timeline entries
        self.memories: Dict[str, Memory] = {}  # memory_id -> Memory
        self.memory_entries: Dict[str, Dict[str, MemoryDataEntry]] = {}  # memory_id -> {data_id: entry}
        self.redis_store = None  # Store API backends when set
        self.postgres_store = None
        self.supabase_store = None
        self.gcs_store = None

    def _check_memories_enabled(self) -> None:
        """No-op for mock; memories are always enabled."""

    def reset(self):
        """Clear all stored data."""
        self.raw_data.clear()
        self.metadata.clear()
        self.timeline.clear()
        self.memories.clear()
        self.memory_entries.clear()
    
    def store_raw_data(
        self, data_id: str, version: int, content: bytes, content_type: str
    ) -> int:
        """Store raw data in memory and return size."""
        if data_id not in self.raw_data:
            self.raw_data[data_id] = {}
        self.raw_data[data_id][version] = (content, content_type)
        return len(content)
    
    def get_raw_data(self, data_id: str, version: Optional[int] = None) -> Tuple[bytes, str]:
        """Get raw data from memory."""
        if data_id not in self.raw_data:
            raise FileNotFoundError(f"Data not found: {data_id}")

        if version is None:
            metadata = self.get_metadata(data_id)
            if metadata is None:
                raise FileNotFoundError(f"Metadata not found for data_id: {data_id}")
            version = metadata.current_version

        if version not in self.raw_data[data_id]:
            raise FileNotFoundError(f"Data not found: {data_id} version {version}")

        return self.raw_data[data_id][version]
    
    def store_metadata(self, metadata: DataMetadata) -> None:
        """Store metadata in memory."""
        self.metadata[metadata.data_id] = metadata
    
    def get_metadata(self, data_id: str) -> Optional[DataMetadata]:
        """Get metadata. Returns None if not found (matches real storage interface)."""
        return self.metadata.get(data_id)
    
    def list_all_metadata(self) -> List[DataListItem]:
        """List all data items."""
        items = []
        for data_id, metadata in self.metadata.items():
            latest_version = metadata.versions[-1] if metadata.versions else None
            items.append(DataListItem(
                data_id=metadata.data_id,
                current_version=metadata.current_version,
                created_at=metadata.created_at,
                updated_at=metadata.updated_at,
                content_type=latest_version.content_type if latest_version else "unknown",
                size=latest_version.size if latest_version else 0
            ))
        items.sort(key=lambda x: x.updated_at, reverse=True)
        return items
    
    def delete_data(self, data_id: str) -> None:
        """Delete all versions of data and metadata."""
        if data_id in self.raw_data:
            del self.raw_data[data_id]
        if data_id in self.metadata:
            del self.metadata[data_id]
    
    def record_timeline(
        self, user: str, data_id: str, version: int, action: str
    ) -> None:
        """Record a timeline entry."""
        import time
        timestamp = int(time.time())
        entry = TimelineEntry(
            user=user,
            data_id=data_id,
            version=version,
            action=action,
            timestamp=timestamp
        )
        if user not in self.timeline:
            self.timeline[user] = []
        self.timeline[user].append(entry)
    
    def get_timeline(self, user: str) -> List[TimelineEntry]:
        """Get timeline for a user."""
        entries = self.timeline.get(user, [])
        return sorted(entries, key=lambda x: x.timestamp, reverse=True)
    
    def create_data(
        self,
        content: bytes,
        content_type: str,
        user: str = "demo",
        memory_ids: Optional[List[str]] = None,
        device_info: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[str, int]:
        """Create new data entry. Returns (data_id, version)."""
        data_id = str(uuid.uuid4())
        version = 1
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        size = self.store_raw_data(data_id, version, content, content_type)
        
        metadata = DataMetadata(
            data_id=data_id,
            current_version=version,
            versions=[
                VersionInfo(
                    version=version,
                    timestamp=timestamp,
                    size=size,
                    content_type=content_type
                )
            ],
            created_at=timestamp,
            updated_at=timestamp,
            name=name,
            description=description,
            memory_ids=memory_ids,
            device_info=device_info,
            tags=tags,
        )
        self.store_metadata(metadata)
        self.record_timeline(user, data_id, version, "create")
        
        return data_id, version
    
    def update_data(
        self, data_id: str, content: bytes, content_type: str, user: str = "demo"
    ) -> int:
        """Update existing data. Returns new version number."""
        metadata = self.get_metadata(data_id)
        new_version = metadata.current_version + 1
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        size = self.store_raw_data(data_id, new_version, content, content_type)
        
        metadata.current_version = new_version
        metadata.versions.append(
            VersionInfo(
                version=new_version,
                timestamp=timestamp,
                size=size,
                content_type=content_type
            )
        )
        metadata.updated_at = timestamp
        self.store_metadata(metadata)
        self.record_timeline(user, data_id, new_version, "update")
        
        return new_version

    # Memory management (for /api/v1/memories tests)
    def create_memory(
        self, memory_create: MemoryCreate, memory_id_override: Optional[str] = None
    ) -> Memory:
        """Create a new memory container."""
        memory_id = memory_id_override or str(uuid.uuid4())
        if memory_id in self.memories:
            raise ValueError(f"Memory ID '{memory_id}' already exists")
        duration = MemoryDuration(MEMORY_TYPE_DURATION[memory_create.memory_type])
        now_str = datetime.utcnow().isoformat() + "Z"
        memory = Memory(
            memory_id=memory_id,
            memory_type=memory_create.memory_type,
            duration=duration,
            name=memory_create.name,
            description=memory_create.description,
            user_id=memory_create.user_id,
            data_ids=[],
            metadata=memory_create.metadata,
            device_id=memory_create.device_id,
            device_info=memory_create.device_info,
            active=True if memory_create.memory_type == MemoryType.SESSION else None,
            expires_at=None,
            created_at=now_str,
            updated_at=now_str,
        )
        self.memories[memory_id] = memory
        self.memory_entries[memory_id] = {}
        return memory

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        return self.memories.get(memory_id)

    def list_memories(
        self,
        user_id: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        duration: Optional[MemoryDuration] = None,
        active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Memory], int]:
        """List memories with optional filters."""
        memories = list(self.memories.values())
        if user_id is not None:
            memories = [m for m in memories if m.user_id == user_id]
        if memory_type is not None:
            memories = [m for m in memories if m.memory_type == memory_type]
        if duration is not None:
            memories = [m for m in memories if m.duration == duration]
        if active is not None:
            memories = [m for m in memories if m.active == active]
        memories.sort(key=lambda x: x.updated_at, reverse=True)
        total = len(memories)
        return memories[skip : skip + limit], total

    def add_data_to_memory(
        self,
        memory_id: str,
        data_id: str,
        action: Optional[str] = None,
        version: Optional[int] = None,
        entry_metadata: Optional[Dict] = None,
    ) -> Optional[Memory]:
        """Associate a data item with a memory."""
        memory = self.get_memory(memory_id)
        if not memory:
            return None
        now_str = datetime.utcnow().isoformat() + "Z"
        entry = MemoryDataEntry(
            data_id=data_id,
            memory_id=memory_id,
            action=action,
            version=version,
            associated_at=now_str,
            metadata=entry_metadata or {},
        )
        if memory_id not in self.memory_entries:
            self.memory_entries[memory_id] = {}
        self.memory_entries[memory_id][data_id] = entry
        if data_id not in memory.data_ids:
            memory.data_ids.append(data_id)
            memory.updated_at = now_str
            self.memories[memory_id] = memory
        return memory

    def get_memory_data_entries(self, memory_id: str) -> List[MemoryDataEntry]:
        """Get raw MemoryDataEntry records for a memory."""
        entries = list(self.memory_entries.get(memory_id, {}).values())
        entries.sort(key=lambda x: x.associated_at, reverse=True)
        return entries

    def update_memory(self, memory_id: str, memory_update: MemoryUpdate) -> Optional[Memory]:
        """Update a memory's metadata."""
        memory = self.get_memory(memory_id)
        if not memory:
            return None
        now_str = datetime.utcnow().isoformat() + "Z"
        if memory_update.name is not None:
            memory.name = memory_update.name
        if memory_update.description is not None:
            memory.description = memory_update.description
        if memory_update.metadata is not None:
            memory.metadata = memory_update.metadata
        if memory_update.active is not None:
            memory.active = memory_update.active
        memory.updated_at = now_str
        self.memories[memory_id] = memory
        return memory

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory and all its data entries."""
        if memory_id not in self.memories:
            return False
        del self.memories[memory_id]
        self.memory_entries.pop(memory_id, None)
        return True

    def remove_data_from_memory(self, memory_id: str, data_id: str) -> Optional[Memory]:
        """Remove a data item from a memory."""
        memory = self.get_memory(memory_id)
        if not memory:
            return None
        if memory_id in self.memory_entries and data_id in self.memory_entries[memory_id]:
            del self.memory_entries[memory_id][data_id]
        if data_id in memory.data_ids:
            memory.data_ids.remove(data_id)
            memory.updated_at = datetime.utcnow().isoformat() + "Z"
            self.memories[memory_id] = memory
        return memory


# Global mock storage instance for tests
_mock_storage = MockStorage()


def get_mock_storage() -> MockStorage:
    """Get the mock storage instance."""
    return _mock_storage


@pytest.fixture
def mock_storage():
    """Fixture providing a clean mock storage for each test."""
    _mock_storage.reset()
    return _mock_storage


@pytest.fixture
def app_with_mock_storage(mock_storage):
    """Fixture providing a FastAPI app with mock storage injected."""
    import app.storage as storage_module

    # Patch get_storage BEFORE importing main, so routers get the patched version
    original_get_storage = storage_module.get_storage
    storage_module.get_storage = lambda: mock_storage

    from main import app

    yield app

    # Restore original
    storage_module.get_storage = original_get_storage


@pytest.fixture
def test_client(app_with_mock_storage):
    """Fixture providing a synchronous test client."""
    return TestClient(app_with_mock_storage)


@pytest.fixture
async def async_client(app_with_mock_storage):
    """Fixture providing an async test client."""
    transport = ASGITransport(app=app_with_mock_storage)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_json_content():
    """Fixture providing sample JSON content."""
    return json.dumps({"message": "Hello, World!", "count": 42})


@pytest.fixture
def sample_binary_content():
    """Fixture providing sample binary content."""
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'


@pytest.fixture
def created_data_item(mock_storage, sample_json_content):
    """Fixture that creates a data item and returns its ID."""
    data_id, version = mock_storage.create_data(
        content=sample_json_content.encode('utf-8'),
        content_type='application/json',
        user='test-user'
    )
    return data_id, version
