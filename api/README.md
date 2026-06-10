# Mem-Dog API

Python FastAPI backend for the Mem-Dog private AI memory platform.

**Version:** 4.0.0

## Features

- RESTful API for data storage with versioning
- Dual storage backends: local filesystem (zero config) or Google Cloud Storage
- Automatic version management
- **Memory system**: Unified context layer with 8 memory types (timeline, session, conversation, user, organizational, factual, episodic, semantic). Data items can belong to multiple memories (many-to-many).
- Support for any file type
- **User Management**:
  - User profiles with roles and status
  - Per-user API keys (`md_*` prefix) with O(1) Supabase lookup + global service key
- **Access Control**:
  - Per-data permissions (public, authenticated, specific users/roles)
- **AI Layer** (optional):
  - Prompts: Create and manage prompt templates
  - Embeddings: Generate vector embeddings for semantic search
  - Viewpoints: AI-powered analysis and interpretations
  - Skills: AI agent role and capability definitions
  - NLP Query: Natural language querying across data
  - 10 Native AI engines: OpenAI, Anthropic, Gemini, Ollama, Bedrock, OpenRouter, Together, HuggingFace, vLLM, LiteLLM
  - 100+ additional providers via LiteLLM gateway (see https://docs.openclaw.ai/providers)

## API Routers

| Router | Prefix | Description |
|--------|--------|-------------|
| `data` | `/api/v1/data` | Core data CRUD operations |
| `versions` | `/api/v1/versions` | Version management |
| `memories` | `/api/v1/memories` | Memory CRUD and data association |
| `list` | `/api/v1/list` | User data listing |
| `users` | `/api/v1/users` | User management |
| `access` | `/api/v1/data/{id}/access` | Access control |
| `bulk_delete` | `/api/v1/bulk` | Bulk data and memory deletion |
| `ai_config` | `/api/v1/ai` | AI configuration |
| `prompts` | `/api/v1/ai/prompts` | Prompt templates |
| `embeddings` | `/api/v1/ai/embeddings` | Vector embeddings |
| `viewpoints` | `/api/v1/ai/viewpoints` | AI viewpoints |
| `skills` | `/api/v1/ai/skills` | AI agent skills |
| `ai_query` | `/api/v1/ai/query` | NLP querying |
| `stats` | `/api/v1/stats` | Platform and per-user statistics |

## API Documentation

Once running, visit:
- `/docs` - Interactive Swagger documentation
- `/redoc` - ReDoc documentation

OpenAPI specification: `docs/openapi.yaml`

## Development

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Run server (local storage is the default — no .env file needed)
uvicorn main:app --reload --port 8080
```

To use GCS instead of local storage, create a `.env` file with your GCP settings (see Environment Variables below).

## Storage Backends

The API supports three storage backends:

| | Local | GCS | Supabase (hybrid) |
|---|---|---|---|
| **Default?** | Yes (no config needed) | When `GCP_PROJECT_ID` is set | When `STORAGE_BACKEND=supabase` |
| **Raw data** | Local filesystem | GCS bucket | GCS bucket |
| **Structured data** | Local filesystem | GCS buckets | Supabase PostgreSQL (`mem_dog_blobs`) |
| **Embeddings** | Local filesystem (JSON) | GCS bucket (JSON) | pgvector table (`mem_dog_embeddings`) |
| **KV Store API** | Not available | Optional (GCS) | Supabase (`store_kv`) |
| **Features** | All enabled automatically | Requires bucket-per-feature config | All enabled automatically |
| **Best for** | Development, personal use | Production, multi-region | Production with structured queries |

The backend is auto-detected but can be forced with `STORAGE_BACKEND=local`, `STORAGE_BACKEND=gcs`, or `STORAGE_BACKEND=supabase`.

### Supabase backend

When `STORAGE_BACKEND=supabase`, the API uses a hybrid approach:

- **Raw binary data** stays in GCS (requires `RAW_BUCKET`)
- **All other data** (metadata, memories, users, viewpoints, prompts, skills, stats, channels, index, AI config) is stored in Supabase PostgreSQL via the `mem_dog_blobs` table
- **Vector embeddings** use a dedicated `mem_dog_embeddings` pgvector table with multi-tenant isolation (all queries scoped by `user_id`)
- **Similarity search** uses pgvector cosine distance via the `match_embeddings` RPC (with automatic fallback to in-memory cosine scan)
- **Paginated listing** uses the `list_data_paginated` RPC for DB-level pagination and tag filtering
- **KV Store API** is backed by the `store_kv` table in Supabase

All features (AI layer, user management, memories, stats) are automatically enabled — no per-feature bucket config needed.

Prerequisites:
1. Apply the schema: `api/supabase/mem_dog_blobs.sql`, `api/supabase/mem_dog_embeddings.sql`, `api/supabase/store_kv.sql`, `api/supabase/list_data_paginated.sql`
2. Set `SUPABASE_URL`, `SUPABASE_KEY` (or `SUPABASE_SERVICE_ROLE_KEY`), and `RAW_BUCKET`

## Environment Variables

### Storage Backend

| Variable | Description | Default |
|----------|-------------|---------|
| `STORAGE_BACKEND` | Force backend: `local`, `gcs`, or `supabase` | Auto-detected |
| `MEM_DOG_DATA_DIR` | Data directory for local storage | `~/.mem-dog` |
| `ENVIRONMENT` | Environment name | `development` |

### GCS Variables (Required only when using GCS backend)

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Your GCP project ID | `memdog-dev` |
| `SYSTEM_CONFIG_BUCKET` | System config bucket (reads all settings from GCS) | `memdog-dev-mem-dog-sysconfig-dev` |
| `RAW_BUCKET` | Bucket name for raw data | `memdog-dev-mem-dog-raw-dev` |
| `META_BUCKET` | Bucket name for metadata | `memdog-dev-mem-dog-meta-dev` |
| `MEMORIES_BUCKET` | Bucket name for memories | `memdog-dev-mem-dog-memories-dev` |
| `USER_BUCKET` | Bucket name for user data | `memdog-dev-mem-dog-users-dev` |

### AI Layer Variables (Optional — GCS mode only; not needed for supabase)

| Variable | Description | Example |
|----------|-------------|---------|
| `PROMPTS_BUCKET` | Bucket for prompt templates | `memdog-dev-mem-dog-prompts-dev` |
| `EMBEDDINGS_BUCKET` | Bucket for vector embeddings | `memdog-dev-mem-dog-embeddings-dev` |
| `VIEWPOINTS_BUCKET` | Bucket for AI analysis | `memdog-dev-mem-dog-viewpoints-dev` |
| `AI_CONFIG_BUCKET` | Bucket for AI configuration | `memdog-dev-mem-dog-aiconfig-dev` |
| `SKILLS_BUCKET` | Bucket for AI agent skills | `memdog-dev-mem-dog-skills-dev` |
| `AI_ENCRYPTION_KEY` | Key for encrypting user API keys | Base64-encoded 32 bytes |

### Supabase Variables (Required only for supabase backend)

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_URL` | Supabase URL (Kong or direct) | `http://supabase-kong.supabase.svc.cluster.local:8000` |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (preferred) | JWT token |
| `SUPABASE_KEY` | Fallback key (if service role not set) | JWT token |
| `SUPABASE_API_GATEWAY_KEY` | API Gateway key (if behind GCP API GW) | API key string |
| `RAW_BUCKET` | GCS bucket for raw binary data | `memdog-dev-mem-dog-raw-dev` |

### System Default AI (Optional)

| Variable | Description | Example |
|----------|-------------|---------|
| `SYSTEM_GEMINI_API_KEY` | System-provided Gemini key for users | Gemini API key |
| `SYSTEM_GEMINI_MODEL_EMBEDDING` | Default embedding model | `text-embedding-004` |
| `SYSTEM_GEMINI_MODEL_COMPLETION` | Default completion model | `gemini-1.5-flash` |

**Important:**
- In **local mode**, no bucket variables are needed — all features are enabled automatically.
- In **GCS mode**, core bucket variables are required; the API will fail to start without them.
- In **supabase mode**, only `SUPABASE_URL`, `SUPABASE_KEY`, and `RAW_BUCKET` are needed — all features are enabled automatically.
- AI layer bucket variables are optional in GCS mode; if not set, AI features will be disabled.
- System Gemini key is optional; if set, users can use "system" mode without their own keys.
- Use `is_ai_enabled()` to check if AI layer is configured.
- Use `is_system_ai_available()` to check if system default is available.

GCS bucket naming convention: `{PROJECT_ID}-mem-dog-{type}-{environment}`

## Docker

```bash
# Build
docker build -t mem-dog-api .

# Run with local storage (default — no GCP needed)
docker run -p 8080:8080 \
  -e STORAGE_BACKEND=local \
  -e MEM_DOG_DATA_DIR=/data \
  -v mem-dog-data:/data \
  mem-dog-api

# Run with GCS backend (core buckets)
docker run -p 8080:8080 \
  -e GCP_PROJECT_ID=memdog-dev \
  -e RAW_BUCKET=memdog-dev-mem-dog-raw-dev \
  -e META_BUCKET=memdog-dev-mem-dog-meta-dev \
  -e MEMORIES_BUCKET=memdog-dev-mem-dog-memories-dev \
  -e USER_BUCKET=memdog-dev-mem-dog-users-dev \
  -e ENVIRONMENT=dev \
  mem-dog-api

# Run with GCS backend + AI layer
docker run -p 8080:8080 \
  -e GCP_PROJECT_ID=memdog-dev \
  -e RAW_BUCKET=memdog-dev-mem-dog-raw-dev \
  -e META_BUCKET=memdog-dev-mem-dog-meta-dev \
  -e MEMORIES_BUCKET=memdog-dev-mem-dog-memories-dev \
  -e PROMPTS_BUCKET=memdog-dev-mem-dog-prompts-dev \
  -e EMBEDDINGS_BUCKET=memdog-dev-mem-dog-embeddings-dev \
  -e VIEWPOINTS_BUCKET=memdog-dev-mem-dog-viewpoints-dev \
  -e AI_CONFIG_BUCKET=memdog-dev-mem-dog-aiconfig-dev \
  -e SKILLS_BUCKET=mem-dog-skills-dev \
  -e ENVIRONMENT=dev \
  mem-dog-api

# Run with Supabase hybrid backend (raw in GCS, everything else in Supabase)
docker run -p 8080:8080 \
  -e STORAGE_BACKEND=supabase \
  -e GCP_PROJECT_ID=memdog-dev \
  -e RAW_BUCKET=memdog-dev-mem-dog-raw-dev \
  -e SUPABASE_URL=http://supabase-kong.supabase.svc.cluster.local:8000 \
  -e SUPABASE_SERVICE_ROLE_KEY=your-service-role-jwt \
  -e ENVIRONMENT=dev \
  mem-dog-api
```

## Cloud Run Deployment

When deploying to Cloud Run, **always include the bucket environment variables**:

```bash
# Core deployment (without AI layer)
gcloud run deploy mem-dog-api-dev \
  --image IMAGE_URL \
  --region us-central1 \
  --set-env-vars GCP_PROJECT_ID=memdog-dev \
  --set-env-vars RAW_BUCKET=memdog-dev-mem-dog-raw-dev \
  --set-env-vars META_BUCKET=memdog-dev-mem-dog-meta-dev \
  --set-env-vars MEMORIES_BUCKET=memdog-dev-mem-dog-memories-dev \
  --set-env-vars USER_BUCKET=memdog-dev-mem-dog-users-dev \
  --set-env-vars ENVIRONMENT=dev
```

Deployment with AI layer enabled:

```bash
gcloud run deploy mem-dog-api-dev \
  --image IMAGE_URL \
  --region us-central1 \
  --set-env-vars GCP_PROJECT_ID=memdog-dev \
  --set-env-vars RAW_BUCKET=memdog-dev-mem-dog-raw-dev \
  --set-env-vars META_BUCKET=memdog-dev-mem-dog-meta-dev \
  --set-env-vars MEMORIES_BUCKET=memdog-dev-mem-dog-memories-dev \
  --set-env-vars USER_BUCKET=memdog-dev-mem-dog-users-dev \
  --set-env-vars PROMPTS_BUCKET=memdog-dev-mem-dog-prompts-dev \
  --set-env-vars EMBEDDINGS_BUCKET=memdog-dev-mem-dog-embeddings-dev \
  --set-env-vars VIEWPOINTS_BUCKET=memdog-dev-mem-dog-viewpoints-dev \
  --set-env-vars AI_CONFIG_BUCKET=memdog-dev-mem-dog-aiconfig-dev \
  --set-env-vars SKILLS_BUCKET=${PROJECT_ID}-mem-dog-skills-${ENV} \
  --set-env-vars ENVIRONMENT=dev
```

If you deployed without these env vars, update the existing service:

```bash
gcloud run services update mem-dog-api-dev \
  --region us-central1 \
  --set-env-vars GCP_PROJECT_ID=memdog-dev \
  --set-env-vars RAW_BUCKET=memdog-dev-mem-dog-raw-dev \
  --set-env-vars META_BUCKET=memdog-dev-mem-dog-meta-dev \
  --set-env-vars MEMORIES_BUCKET=memdog-dev-mem-dog-memories-dev \
  --set-env-vars USER_BUCKET=memdog-dev-mem-dog-users-dev \
  --set-env-vars PROMPTS_BUCKET=memdog-dev-mem-dog-prompts-dev \
  --set-env-vars EMBEDDINGS_BUCKET=memdog-dev-mem-dog-embeddings-dev \
  --set-env-vars VIEWPOINTS_BUCKET=memdog-dev-mem-dog-viewpoints-dev \
  --set-env-vars AI_CONFIG_BUCKET=memdog-dev-mem-dog-aiconfig-dev \
  --set-env-vars ENVIRONMENT=dev
```

## Testing

```bash
# Install test dependencies
uv pip install pytest pytest-asyncio httpx

# Run tests
pytest
```
