# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mem-dog is a multi-channel data ingestion and AI enrichment platform. Data flows from external channels through a gateway, gets stored via the API, and optionally processed by a 42-agent webhook pipeline for classification, analysis, and embedding generation.

## Architecture

**Data flow:** Channels → webhook-gateway → API (ingest) + Webhook Pipeline (NATS). The pipeline writes enriched results back to the API, which dual-writes entities to both Postgres and Neo4j (Graphiti). DigiMe (openclaw-node) is a separate AI agent that communicates with the mem-dog RAG system.

- **api/** — FastAPI (Python 3.12, `pyproject.toml`) backend. Entry: `api/main.py`. Storage abstraction supports local filesystem, GCS, and Supabase backends (controlled by `STORAGE_BACKEND` env var). Supabase SQL migrations in `api/supabase/`. Neo4j/Graphiti integration for temporal knowledge graph.
- **ui/** — Next.js 14 (TypeScript) frontend. Talks to the API via proxy rewrites in `ui/next.config.js` (`/api/v1/*` → API, `/auth/v1/*` → GoTrue). `NEXT_PUBLIC_*` env vars are baked at Docker **build time**, not runtime.
- **webhook/processor/** — NATS pull worker + ADK agent with 42 typed sub-agents for AI enrichment. Requires Python ≥3.12 and `uv` for dependency management. Sub-agent routing uses 6-layer data type detection (see `webhook/processor/webhook_agent/router.py`). Agent registry in `webhook/processor/webhook_agent/sub_agents/__init__.py`.
- **webhook/receiver/** — HTTP receiver that publishes to NATS.
- **webhook-gateway/** — FastAPI (Python ≥3.11, `pyproject.toml`) service that normalizes channel messages into UniversalEnvelope format. Supports multiple LLM providers via litellm, channel policies, rate limiting, and credential-injecting integration proxy. CLI entry point: `wgw`.
- **openclaw-node/** — DigiMe AI agent (OpenClaw runtime) that communicates with the mem-dog RAG system to answer queries, search, and ingest data through conversation. Separate from the webhook pipeline.
- **client/** — Python SDK (`mem_dog_client`) using httpx. Mirrors REST API with 70+ methods.
- **clients/** — Multi-language SDKs: TypeScript (native fetch), Go (stdlib), Rust (async tokio), Ruby.
- **k8s/** — Kubernetes manifests for GKE + Supabase. Namespaces: `mem-dog` (API), `webhook-pipeline`, `webhook-gateway` (gateway + openclaw-node), `supabase`.
- **testing/** — Test configs live here, separate from app code. `testing/ui/` has Jest + Playwright configs; `testing/api/` has pytest fixtures with mock storage.

## Common Commands

### Local Development

```bash
docker compose up                    # Start full stack (10 services)
# UI: localhost:3000, API: localhost:8080, Gateway: localhost:8070
# Neo4j: localhost:7474 (browser), bolt://localhost:7687
# Includes 3 Ollama instances (small/medium/large tiers), Redis, PostgreSQL 16 + pgvector, Neo4j
```

### API (from api/)

```bash
uvicorn main:app --reload --port 8080    # Dev server
pytest                                    # All tests (uses pytest-asyncio)
pytest tests/test_foo.py -v               # Single test file
pytest tests/test_foo.py::test_bar -v     # Single test
```

### UI (from ui/)

```bash
npm run dev                  # Dev server (port 3000)
npm run build                # Production build
npm run test:unit            # Jest unit tests
npm run test:unit:watch      # Watch mode
npm run test:e2e             # Playwright E2E tests
npm run lint                 # ESLint
```

### Webhook Processor (from webhook/processor/)

```bash
make install          # Install deps (requires uv)
make agent            # Start ADK agent (port 8080)
make model-server     # Start local LLM server (port 8081)
make processor        # Start Cloud Function (port 8082)
make test             # Send test payload
make test-cf          # Send test via Cloud Function (Pub/Sub)
make health           # Check agent health
make model-health     # Check model server health
make list-apps        # List available apps
# GPU support: N_GPU_LAYERS=99 make model-server (Apple Metal)
```

### Deployment

```bash
# API → GKE
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-api-gke -p memdog-dev -e dev

# UI → Cloud Run
./scripts/manual-deploy.sh deploy-ui -p memdog-dev -e dev

# Webhook Pipeline → GKE
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-webhook-pipeline-gke -p memdog-dev -e dev

# Also available: deploy-webhook-gateway-gke, deploy-openclaw-node-gke, deploy-supabase-gke,
# deploy-model-servers, deploy-redis, setup-env, setup-postgres, setup-supabase
```

## Search & Knowledge Graph

- **5 search modes**: vector (pgvector cosine), fts (BM25 keyword), hybrid (vector + BM25 via RRF), graph (Graphiti BFS on Neo4j), full (all signals merged)
- **4 rerankers**: none, RRF (rank fusion), MMR (diversity), cross-encoder (LLM-scored)
- **Knowledge graph**: Dual-layer — Postgres (always active) + Graphiti/Neo4j (optional, temporal). Entities dual-written to both. Graphiti adds `valid_at`/`invalid_at` timestamps for point-in-time fact retrieval.
- **RAG chat**: `/api/v1/ai/query/chat` — conversational answers with `[1][2]` citation markers

## Key Design Patterns

- **IDs**: ULID-based — `data_<ulid>` for data items, `mem_<type>_<ulid>` for memories
- **10 memory types**: timeline, session, conversation, user, organizational, factual, episodic, semantic, custom, tracing — grouped into **4 Mem0 categories**: conversation, session, user, organizational
- **Memory access levels**: private (default), shared, public, restricted — with `shared_with` user list for shared/restricted
- **Memory expiry**: Default TTL per type (conversation=1h, session=24h, timeline=7d, tracing=3d, long-term=never). Override with `ttl_hours` or `no_expiry=true`
- **Storage backends**: local (default, `~/.mem-dog`), GCS (production), Supabase (hybrid with pgvector). Auto-detection priority: explicit `STORAGE_BACKEND` → `GCP_PROJECT_ID` → `SYSTEM_CONFIG_BUCKET` → `local`. Supabase hybrid mode stores raw binary in GCS and all structured data (metadata, memories, embeddings) in Postgres.
- **Authentication**: JWT from Supabase (`sub` claim, auto-creates user profile on first login via `ensure_jwt_user_profile`) + per-user API keys (`md_*` prefix, O(1) Supabase lookup). Auth middleware sets `request.state.user_id` and `request.state.auth_type`.
- **Encryption**: Nango AES-256-GCM for integration credentials; Fernet (`api/app/crypto.py`) for AI provider API keys.
- **AI models**: Tiered by data complexity — small (Gemma3:4b), medium (12b), large (27b), multimodal (Qwen3-VL), omni (Qwen3.5). Config in `config/ai.env`. Model Garden supports 10+ providers with per-user/per-type routing and fallback chains (Ollama → Ollama Cloud → Gemini).
- **Sub-agent routing**: 6-layer detection in `webhook/processor/webhook_agent/router.py` — explicit field → LLM classifier → MIME registry → URL extension → fallback to BinaryBlobAgent
- **Integration platform**: Powered by Nango (self-hosted, `nango` namespace). 300+ providers with OAuth2/API-key connections, automatic token refresh, AES-256-GCM credential encryption. API adapter layer in `api/app/routers/integrations.py` proxies to Nango. Per-user webhook endpoints (`whk_<ulid>`) in `api/app/routers/webhooks_mgmt.py`. See `docs/integrations/integrations.md`.

## Important Relationships

- When changing webhook agent code (`model_client.py`, `llm_utils.py`, `api_client/`), the webhook pipeline must also be redeployed.
- When changing integration router/models (`api/app/routers/integrations.py`, `api/app/nango_client.py`), redeploy the API. When changing `webhook-gateway/app/credentials.py`, redeploy the webhook gateway. Nango (`nango` namespace) is independent — restart only if changing Nango config/secrets.
- API routers live in `api/app/routers/` (33 routers). Models in `api/app/models.py`.
- UI components in `ui/src/components/`. Path alias: `@/*` → `src/*`.
- Shared AI config: `config/ai.env`.
- Test configs for UI are in `testing/ui/` (separate from app code).
