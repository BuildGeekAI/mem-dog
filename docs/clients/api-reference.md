# API Reference -- Full Method List

Complete list of all ~120 API endpoints covered by the mem-dog SDKs, organized by category. Each method maps 1:1 to an OpenAPI operation.

## Health & Auth

| Endpoint | Python | TypeScript | Go | Rust | Ruby |
|----------|--------|------------|-----|------|------|
| `GET /` | `root()` | `root()` | `Root()` | `root()` | `root` |
| `GET /health` | `health()` | `health()` | `Health()` | `health()` | `health` |
| `GET /api/v1/auth/me` | `get_me()` | `getMe()` | `GetMe()` | `get_me()` | `get_me` |

## Data

| Endpoint | Python | TypeScript | Go | Rust | Ruby |
|----------|--------|------------|-----|------|------|
| `POST /api/v1/data` | `create_data()` | `createData()` | `CreateData()` | `create_data()` | `create_data` |
| `GET /api/v1/data` | `list_data()` | `listData()` | `ListData()` | `list_data()` | `list_data` |
| `GET /api/v1/data/{id}` | `get_data()` | `getData()` | `GetData()` | `get_data()` | `get_data` |
| `PUT /api/v1/data/{id}` | `update_data()` | `updateData()` | `UpdateData()` | -- | `update_data` |
| `DELETE /api/v1/data/{id}` | `delete_data()` | `deleteData()` | `DeleteData()` | `delete_data()` | `delete_data` |
| `GET /api/v1/data/{id}/metadata` | `get_metadata()` | `getMetadata()` | `GetMetadata()` | `get_metadata()` | `get_metadata` |
| `GET /api/v1/data/{id}/info` | `get_info()` | `getInfo()` | `GetInfo()` | `get_info()` | `get_info` |
| `PUT /api/v1/data/{id}/info` | `update_info()` | `updateInfo()` | `UpdateInfo()` | `update_info()` | `update_info` |

## Tags

| Endpoint | Python | TypeScript |
|----------|--------|------------|
| `GET /api/v1/data/{id}/tags` | `get_tags()` | `getTags()` |
| `PUT /api/v1/data/{id}/tags` | `update_tags()` | `updateTags()` |
| `POST /api/v1/data/{id}/tags/add` | `add_tags()` | `addTags()` |
| `POST /api/v1/data/{id}/tags/remove` | `remove_tags()` | `removeTags()` |
| `GET /api/v1/tags` | `list_tags()` | `listAllTags()` |
| `GET /api/v1/tags/search` | `search_tags()` | `searchByTags()` |

## Versions

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/versions/{id}` | `list_versions` / `listVersions` |
| `GET /api/v1/versions/{id}/{v}` | `get_version` / `getVersion` |

## Memories

| Endpoint | Method |
|----------|--------|
| `POST /api/v1/memories` | `create_memory` |
| `GET /api/v1/memories` | `list_memories` |
| `GET /api/v1/memories/{id}` | `get_memory` |
| `PUT /api/v1/memories/{id}` | `update_memory` |
| `DELETE /api/v1/memories/{id}` | `delete_memory` |
| `POST /api/v1/memories/{id}/data` | `add_data_to_memory` |
| `GET /api/v1/memories/{id}/data` | `get_memory_data` |
| `GET /api/v1/memories/{id}/entries` | `get_memory_entries` |
| `DELETE /api/v1/memories/{id}/data/{did}` | `remove_data_from_memory` |
| `POST /api/v1/memories/{id}/compress` | `compress_memory` |

## Search & AI

| Endpoint | Method |
|----------|--------|
| `POST /api/v1/ai/query` | `ai_query` / `aiQuery` |
| `POST /api/v1/ai/query/semantic` | `semantic_search` / `semanticSearch` |
| `POST /api/v1/ai/query/chat` | `chat` |
| `POST /api/v1/ai/query/timeline` | `timeline_query` / `timelineQuery` |
| `GET /api/v1/ai/query/test` | `ai_query_test` / `aiQueryTest` |
| `GET /api/v1/ai/system-config` | `get_system_config` / `getSystemConfig` |
| `GET /api/v1/ai/model-catalog` | `get_model_catalog` / `getModelCatalog` |
| `GET /api/v1/ai/model-catalog/{id}` | `get_model_details` / `getModelDetails` |

## Embeddings

| Endpoint | Method |
|----------|--------|
| `POST /api/v1/ai/embeddings` | `create_embedding` |
| `GET /api/v1/ai/embeddings` | `list_embeddings` |
| `GET /api/v1/ai/embeddings/{id}` | `get_embedding` |
| `DELETE /api/v1/ai/embeddings/{id}` | `delete_embedding` |
| `GET /api/v1/ai/embeddings/data/{id}` | `get_data_embeddings` |
| `DELETE /api/v1/ai/embeddings/data/{id}` | `delete_data_embeddings` |
| `POST /api/v1/ai/embeddings/bulk-delete` | `bulk_delete_embeddings` |

## Viewpoints

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/ai/viewpoints` | `list_viewpoints` |
| `POST /api/v1/ai/viewpoints` | `create_viewpoint` |
| `GET /api/v1/ai/viewpoints/{id}` | `get_viewpoint` |
| `PUT /api/v1/ai/viewpoints/{id}` | `update_viewpoint` |
| `DELETE /api/v1/ai/viewpoints/{id}` | `delete_viewpoint` |
| `GET /api/v1/ai/viewpoints/{id}/history` | `get_viewpoint_history` |
| `GET /api/v1/ai/viewpoints/data/{id}` | `get_data_viewpoints` |
| `POST /api/v1/ai/viewpoints/bulk-delete` | `bulk_delete_viewpoints` |

## Prompts

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/ai/prompts` | `list_prompts` |
| `POST /api/v1/ai/prompts` | `create_prompt` |
| `GET /api/v1/ai/prompts/{id}` | `get_prompt` |
| `PUT /api/v1/ai/prompts/{id}` | `update_prompt` |
| `DELETE /api/v1/ai/prompts/{id}` | `delete_prompt` |

## Skills

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/ai/skills` | `list_skills` |
| `POST /api/v1/ai/skills` | `create_skill` |
| `GET /api/v1/ai/skills/{id}` | `get_skill` |
| `PUT /api/v1/ai/skills/{id}` | `update_skill` |
| `DELETE /api/v1/ai/skills/{id}` | `delete_skill` |

## Analysis Templates

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/ai/analysis-templates` | `list_analysis_templates` |
| `POST /api/v1/ai/analysis-templates` | `create_analysis_template` |
| `POST /api/v1/ai/analysis-templates/seed` | `seed_analysis_templates` |
| `GET /api/v1/ai/analysis-templates/{id}` | `get_analysis_template` |
| `PUT /api/v1/ai/analysis-templates/{id}` | `update_analysis_template` |
| `DELETE /api/v1/ai/analysis-templates/{id}` | `delete_analysis_template` |

## Agent Configs

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/ai/agent-configs` | `list_agent_configs` |
| `POST /api/v1/ai/agent-configs` | `create_agent_config` |
| `GET /api/v1/ai/agent-configs/resolve/{type}` | `resolve_agent_config` |
| `GET /api/v1/ai/agent-configs/{id}` | `get_agent_config` |
| `PUT /api/v1/ai/agent-configs/{id}` | `update_agent_config` |
| `DELETE /api/v1/ai/agent-configs/{id}` | `delete_agent_config` |

## Webhooks

| Endpoint | Method |
|----------|--------|
| `POST /api/v1/webhooks` | `create_webhook` |
| `GET /api/v1/webhooks` | `list_webhooks` |
| `GET /api/v1/webhooks/{id}` | `get_webhook` |
| `PATCH /api/v1/webhooks/{id}` | `update_webhook` |
| `DELETE /api/v1/webhooks/{id}` | `delete_webhook` |
| `POST /api/v1/webhooks/{id}/rotate-secret` | `rotate_webhook_secret` |
| `GET /api/v1/webhooks/{id}/events` | `list_webhook_events` |
| `GET /api/v1/webhooks/{id}/stats` | `get_webhook_stats` |

## Integrations

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/integrations/config` | `list_providers` |
| `GET /api/v1/integrations/config/{key}` | `get_provider` |
| `GET /api/v1/integrations/connections` | `list_connections` |
| `POST /api/v1/integrations/connections` | `create_connection` |
| `GET /api/v1/integrations/connections/{id}` | `get_connection` |
| `PATCH /api/v1/integrations/connections/{id}` | `update_connection` |
| `DELETE /api/v1/integrations/connections/{id}` | `delete_connection` |
| `GET /api/v1/integrations/oauth/authorize` | `get_oauth_url` |
| `POST /api/v1/integrations/oauth/callback` | `oauth_callback` |

## Graph (Knowledge Graph)

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/graph/entities` | `search_entities` |
| `POST /api/v1/graph/entities/batch` | `batch_create_entities` |
| `GET /api/v1/graph/entities/{id}` | `get_entity` |
| `DELETE /api/v1/graph/entities/{id}` | `delete_entity` |
| `GET /api/v1/graph/entities/{id}/relationships` | `get_entity_relationships` |
| `GET /api/v1/graph/data/{id}/entities` | `get_data_entities` |
| `DELETE /api/v1/graph/data/{id}/entities` | `delete_data_entities` |
| `GET /api/v1/graph/facts` | `query_facts` |
| `GET /api/v1/graph/facts/timeline` | `get_fact_timeline` |

## Users, Organizations, Projects

Standard CRUD operations for user management, organization multi-tenancy, and project scoping. See individual SDK docs for full signatures.

## Store (Key-Value)

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/store` | `list_store_keys` |
| `GET /api/v1/store/{key}` | `get_store_value` |
| `PUT /api/v1/store/{key}` | `set_store_value` |
| `DELETE /api/v1/store/{key}` | `delete_store_value` |

## Channels

| Endpoint | Method |
|----------|--------|
| `POST /api/v1/channel-identities` | `create_channel_identity` |
| `GET /api/v1/channel-identities/by-channel` | `get_channel_identity` |
| `PATCH /api/v1/channel-identities/by-channel` | `update_channel_identity` |
| `DELETE /api/v1/channel-identities/by-channel` | `delete_channel_identity` |
| `GET /api/v1/channel-identities/by-user/{id}` | `list_user_channel_identities` |
| `GET /api/v1/channels` | `list_channels` |
| `GET /api/v1/channels/{type}` | `get_channel` |
| `PUT /api/v1/channels/{type}` | `update_channel` |
| `DELETE /api/v1/channels/{type}` | `delete_channel` |

## Stats

| Endpoint | Method |
|----------|--------|
| `GET /api/v1/stats` | `get_stats` |
| `GET /api/v1/stats/data` | `get_data_stats` |
| `GET /api/v1/stats/memories` | `get_memory_stats` |
| `GET /api/v1/stats/embeddings` | `get_embedding_stats` |
| `GET /api/v1/stats/viewpoints` | `get_viewpoint_stats` |
| `GET /api/v1/stats/users/{id}` | `get_user_stats` |
| `POST /api/v1/stats/refresh` | `refresh_stats` |
| `POST /api/v1/stats/refresh/users/{id}` | `refresh_user_stats` |
| `GET /api/v1/stats/agent-types` | `get_agent_type_counts` |
| `POST /api/v1/stats/agent-types/{t}/increment` | `increment_agent_type` |
| `POST /api/v1/stats/agent-types/{t}/decrement` | `decrement_agent_type` |
| `POST /api/v1/stats/token-usage` | `record_token_usage` |
| `GET /api/v1/stats/token-usage/{id}` | `get_token_usage` |
| `DELETE /api/v1/stats/token-usage/{id}` | `delete_token_usage` |

## Ingest

| Endpoint | Method |
|----------|--------|
| `POST /api/v1/ingest` | `ingest` |
