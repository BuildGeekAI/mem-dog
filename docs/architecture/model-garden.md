# Model Garden

Unified provider management for AI engines. Configure API keys, test connectivity, discover models, and feed them into the Smart Routing system.

## Overview

Model Garden lets each user configure their own AI providers (OpenAI, Anthropic, Gemini, Ollama, etc.) with encrypted API key storage in Supabase. Configured providers feed into Smart Routing, giving users full control over which models process their data.

## Architecture

```
UI (ModelGarden.tsx)
  |
  v
API (ai_config.py)
  |-- GET  /api/v1/ai/provider-registry        → static provider catalog
  |-- POST /api/v1/ai/users/{uid}/engines       → create engine
  |-- POST /api/v1/ai/users/{uid}/engines/{eid}/test           → test connectivity
  |-- POST /api/v1/ai/users/{uid}/engines/{eid}/discover-models → discover models
  |-- GET  /api/v1/ai/users/{uid}/available-models             → aggregated model list
  |-- GET  /api/v1/ai/users/{uid}/engines/{eid}/credentials    → decrypted key (internal)
  |
  v
Storage ({user_id}/engines/{engine_id}.json)
  |
  v
Webhook Processor (model_client.py)
  |-- _resolve_credentials() → user engine → env var fallback
```

## Supported Providers

| Provider | Category | Auth | Test | Discover |
|----------|----------|------|------|----------|
| OpenAI | cloud | Bearer token | `GET /models` | `data[].id` |
| Anthropic | cloud | `x-api-key` | `GET /v1/models` | `data[].id` |
| Google Gemini | cloud | URL `?key=` | `GET /v1beta/models` | `models[].name` |
| Ollama (local) | local | None | `GET /api/tags` | `models[].name` |
| OpenRouter | cloud | Bearer token | `GET /v1/models` | `data[].id` |
| Together AI | cloud | Bearer token | `GET /v1/models` | `data[].id` |
| Hugging Face | cloud | Bearer token | Default models | Default models |
| Amazon Bedrock | cloud | AWS SDK | Not supported | Default models |
| vLLM | local | Optional Bearer | `GET /v1/models` | `data[].id` |
| LiteLLM Gateway | gateway | Optional Bearer | `GET /models` | `data[].id` |

## Per-User Isolation

All engine configs are stored under `{user_id}/engines/` in the storage backend. Each user has their own:
- Configured providers with encrypted API keys
- Discovered model lists
- Test status and connectivity results
- Available models aggregation (user engines + system providers)

## API Key Encryption

API keys are encrypted at rest using Fernet (AES-256) via `app/crypto.py`. The encryption key is set via `MASTER_ENCRYPTION_KEY` env var.

- **Create/Update**: Plain text key → `encrypt_api_key()` → stored as `api_key_encrypted`
- **API responses**: Never return encrypted keys; return `has_api_key: bool` instead
- **Internal use**: `decrypt_api_key()` called only for test/discover/credentials endpoints
- **Fallback**: If encryption is unavailable, keys are stored as plain text with a warning

## Backward Compatibility

- **Env vars still work**: `OLLAMA_CLOUD_API_KEY`, `SYSTEM_GEMINI_API_KEY`, `config/ai.env` remain the fallback when no user engine is configured
- **`ai_key_mode` preserved**: `"system"` = env var keys, `"custom"` = Model Garden engines
- **No migration needed**: New fields (`discovered_models`, `last_tested_at`, etc.) all have Pydantic defaults
- **Smart Routing**: Falls back to Ollama Cloud + Catalog + Gemini models if `available-models` endpoint fails

## Webhook Processor Integration

The webhook processor resolves credentials per-request via `_resolve_credentials()`:

1. **User engine** — fetch from `/api/v1/ai/users/{uid}/engines/{eid}/credentials` (5-min cache)
2. **Env var** — `OLLAMA_CLOUD_API_KEY` for Ollama, etc.
3. **Empty** — no credentials (triggers model server or error)

## Files

| File | Purpose |
|------|---------|
| `api/app/provider_registry.py` | Static provider catalog |
| `api/app/provider_service.py` | Test/discover HTTP logic |
| `api/app/models.py` | `ProviderInfo`, extended `AIEngineConfig` |
| `api/app/routers/ai_config.py` | API endpoints (5 new) |
| `api/app/crypto.py` | Fernet encryption helpers |
| `ui/src/components/ModelGarden.tsx` | Model Garden UI |
| `ui/src/components/AIManager.tsx` | Tab integration |
| `ui/src/components/SmartRoutingTab.tsx` | Dynamic model list |
| `webhook/processor/webhook_agent/model_client.py` | Credential resolution |
| `webhook/processor/webhook_agent/api_client/ai.py` | Credential fetch method |
