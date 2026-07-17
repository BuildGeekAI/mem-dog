# Python SDK

The Python SDK (`mem_dog_client`) is the reference implementation for the mem-dog API. It uses `httpx` for HTTP and provides both a full client and a simple facade.

## Installation

```bash
cd clients/python
pip install -e .
```

### Optional Framework Adapters

```bash
pip install -e ".[langchain]"   # LangChain ChatHistory + Retriever
pip install -e ".[crewai]"     # CrewAI memory backend
pip install -e ".[openai]"     # OpenAI function-calling tools
```

## Quick Start

```python
from mem_dog_client import MemDog

m = MemDog("http://localhost:8080", api_key="md_your_key")

# Store data
result = m.add("Hello world", tags=["greeting"])
print(result["data_id"])

# Search
results = m.search("hello", limit=5)

# AI-powered search
results = m.search("what greetings do we have?", use_ai=True)

# Retrieve
item = m.get(result["data_id"])

# Delete
m.delete(result["data_id"])
```

## Full Client

All methods return `httpx.Response`. Call `.json()` to parse, `.raise_for_status()` to check errors.

```python
from mem_dog_client import MemDogClient

client = MemDogClient(
    base_url="http://localhost:8080",
    api_key="md_your_key",
    timeout=30.0,
    org_id=None,       # optional org scope
    project_id=None,   # optional project scope
)
```

### API Coverage

| Category            | Methods |
|---------------------|---------|
| Health & Auth       | `root`, `health`, `get_me` |
| Data                | `create_data`, `list_data`, `get_data`, `get_metadata`, `get_info`, `update_info`, `update_data`, `delete_data` |
| Tags                | `get_tags`, `update_tags`, `add_tags`, `remove_tags`, `list_tags`, `search_tags` |
| Versions            | `list_versions`, `get_version` |
| List                | `list_user_data`, `list_user_data_item` |
| Access Control      | `get_access`, `update_access`, `check_access` |
| Memories            | `create_memory`, `list_memories`, `get_memory`, `update_memory`, `delete_memory`, `get_memory_data`, `add_data_to_memory`, `remove_data_from_memory`, `get_memory_entries`, `compress_memory` |
| Bulk                | `bulk_delete_data`, `bulk_delete_memories`, `bulk_delete_user_data`, `bulk_delete_memory_data` |
| Users               | `list_users`, `get_user`, `create_user`, `update_user`, `delete_user`, `get_user_by_username`, `list_api_keys`, `create_api_key`, `delete_api_key`, `dump_user_data`, `get_user_data`, `create_user_data` |
| Host SaaS           | `create_host_workspace`, `get_host_workspace`, `purge_host_workspace`, `purge_host_workspace_by_project`, `export_host_workspace`, `list_host_api_keys`, `create_host_api_key`, `revoke_host_api_key`, `rotate_host_api_key`, `upsert_data` |
| Organizations       | `create_organization`, `list_organizations`, `get_organization`, `update_organization`, `delete_organization`, `add_org_member`, `list_org_members`, `update_org_member`, `remove_org_member` |
| Projects            | `create_project`, `list_projects`, `get_project`, `update_project`, `delete_project` |
| Channels            | `create_channel_identity`, `get_channel_identity`, `update_channel_identity`, `delete_channel_identity`, `list_user_channel_identities`, `list_channels`, `get_channel`, `update_channel`, `delete_channel` |
| AI Config           | `get_system_config`, `get_model_catalog`, `get_model_details`, `get_ai_engines_available`, `get_ai_system`, `list_ai_engines`, `get_ai_engine`, `create_ai_engine`, `update_ai_engine`, `delete_ai_engine` |
| Search              | `ai_query`, `semantic_search`, `chat`, `timeline_query`, `ai_query_test` |
| Embeddings          | `create_embedding`, `get_embedding`, `list_embeddings`, `delete_embedding`, `get_data_embeddings`, `delete_data_embeddings`, `bulk_delete_embeddings` |
| Prompts             | `list_prompts`, `create_prompt`, `get_prompt`, `update_prompt`, `delete_prompt` |
| Viewpoints          | `list_viewpoints`, `create_viewpoint`, `get_viewpoint`, `update_viewpoint`, `delete_viewpoint`, `get_viewpoint_history`, `get_data_viewpoints`, `bulk_delete_viewpoints` |
| Skills              | `list_skills`, `create_skill`, `get_skill`, `update_skill`, `delete_skill` |
| Analysis Templates  | `list_analysis_templates`, `create_analysis_template`, `seed_analysis_templates`, `get_analysis_template`, `update_analysis_template`, `delete_analysis_template` |
| Agent Configs       | `list_agent_configs`, `create_agent_config`, `resolve_agent_config`, `get_agent_config`, `update_agent_config`, `delete_agent_config` |
| Webhooks            | `create_webhook`, `list_webhooks`, `get_webhook`, `update_webhook`, `delete_webhook`, `rotate_webhook_secret`, `list_webhook_events`, `get_webhook_stats` |
| Integrations        | `list_providers`, `get_provider`, `list_connections`, `create_connection`, `get_connection`, `update_connection`, `delete_connection`, `get_oauth_url`, `oauth_callback` |
| Graph               | `search_entities`, `get_entity`, `get_entity_relationships`, `get_data_entities`, `batch_create_entities`, `delete_entity`, `delete_data_entities`, `query_facts`, `get_fact_timeline` |
| Stats               | `get_stats`, `get_user_stats`, `get_data_stats`, `get_memory_stats`, `get_embedding_stats`, `get_viewpoint_stats`, `refresh_stats`, `refresh_user_stats`, `get_agent_type_counts`, `increment_agent_type`, `decrement_agent_type`, `record_token_usage`, `get_token_usage`, `delete_token_usage` |
| Store               | `list_store_keys`, `get_store_value`, `set_store_value`, `delete_store_value` |
| Ingest              | `ingest` |

### Search Examples

```python
# Semantic search with 5 modes
# limit maps to API max_results (honored server-side; older SDKs silently capped at 5)
resp = client.semantic_search("quarterly revenue", search_mode="hybrid", reranker="rrf", limit=10)

# RAG chat with citation markers
resp = client.chat("What happened last quarter?", search_mode="full", conversation_history=[
    {"role": "user", "content": "Tell me about Q1"},
    {"role": "assistant", "content": "Q1 revenue was..."}
])

# Temporal graph queries
resp = client.query_facts(q="CEO of Acme", at="2024-06-01T00:00:00Z")

# Last remaining API key requires allow_empty=True
# client.delete_api_key(user_id, key_id, allow_empty=True)
```

## Framework Adapters

### LangChain

```python
from mem_dog_client.adapters.langchain import MemDogChatMessageHistory, MemDogRetriever

# Chat history
history = MemDogChatMessageHistory(
    base_url="http://localhost:8080",
    api_key="key",
    memory_id="mem_conv_01HX...",
)

# Retriever for RAG chains
retriever = MemDogRetriever(
    base_url="http://localhost:8080",
    api_key="key",
    search_kwargs={"limit": 5},
)
```

### CrewAI

```python
from mem_dog_client.adapters.crewai import MemDogCrewMemory

memory = MemDogCrewMemory(
    base_url="http://localhost:8080",
    api_key="key",
)
memory.save("Important finding", tags=["research"])
results = memory.search("findings", limit=10)
```

### OpenAI Function Calling

```python
from mem_dog_client import MemDog
from mem_dog_client.adapters.openai import get_mem_dog_tools, handle_mem_dog_tool_call

m = MemDog("http://localhost:8080", api_key="key")
tools = get_mem_dog_tools()  # Returns OpenAI tool definitions

# In your chat loop:
result = handle_mem_dog_tool_call(m, function_name, arguments)
```
