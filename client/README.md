# Mem-Dog Python Client

Python client for the Mem-Dog private AI system API. Talks to the API layer via REST, matching the [OpenAPI specification](../docs/openapi.yaml).

## Installation

```bash
pip install -r requirements.txt
# Or install the package in development mode:
pip install -e .
```

## Usage

```python
from mem_dog_client import MemDogClient

# Connect to local API (default: http://localhost:8080)
client = MemDogClient()

# Or with API key and custom base URL
client = MemDogClient(
    base_url="https://your-api.example.com",
    api_key="your-api-key",
)

# Root and health
info = client.root().json()
client.health().raise_for_status()

# Data operations
resp = client.create_data(content='{"note": "hello"}', name="my-note")
data_id = resp.json()["data_id"]

items = client.list_data().json()
content = client.get_data(data_id).content
metadata = client.get_metadata(data_id).json()

# Create with file
with open("document.pdf", "rb") as f:
    client.create_data(file=f, name="document.pdf", tags=["work"])

# Tags
client.add_tags(data_id, ["important"])
client.get_tags(data_id).json()

# Memories
mem = client.create_memory({
    "memory_type": "timeline",
    "name": "My Timeline",
    "user_id": "default",
}).json()
client.add_data_to_memory(mem["memory_id"], [data_id])

# Users and API keys (when user management is enabled)
users = client.list_users().json()
keys = client.list_api_keys(user_id).json()
client.create_api_key(user_id, name="my-key")

# AI (when AI layer is enabled)
engines = client.get_ai_engines_available().json()
resp = client.ai_query("Summarize the key points", data_ids=[data_id])
```

## API Reference

The client mirrors the Mem-Dog REST API. All methods return `httpx.Response`. Call `.raise_for_status()` to raise on 4xx/5xx, or `.json()` to parse JSON.

| Group   | Methods                                                           |
|---------|-------------------------------------------------------------------|
| Data    | `create_data`, `list_data`, `get_data`, `get_metadata`, `update_data`, `delete_data` |
| Access  | `get_access`, `update_access`, `check_access`                     |
| Tags    | `get_tags`, `update_tags`, `add_tags`, `remove_tags`, `list_tags`, `search_tags` |
| Versions| `list_versions`                                                   |
| List    | `list_user_data`, `list_user_data_item`                           |
| Memories| `create_memory`, `list_memories`, `get_memory`, `update_memory`, `delete_memory`, `get_memory_data`, `add_data_to_memory`, `remove_data_from_memory`, `bulk_delete_memories` |
| Bulk    | `bulk_delete_data`                                                |
| Users   | `list_users`, `get_user`, `create_user`, `update_user`, `delete_user`, `list_api_keys`, `create_api_key`, `delete_api_key` |
| AI      | `get_ai_engines_available`, `list_ai_engines`, `create_ai_engine`, `ai_query`, `create_embedding`, `list_prompts`, `create_prompt`, `list_viewpoints`, `create_viewpoint`, `list_skills`, `create_skill`, etc. |
| Stats   | `get_stats`, `get_user_stats`                                     |

## Authentication

Pass `api_key` when creating the client. It is sent as `Authorization: Bearer <key>`.

```python
client = MemDogClient(api_key="memdog-key-abc123...")
```
