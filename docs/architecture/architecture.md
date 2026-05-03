# Architecture

## System Overview

```
  300+ Apps                         Users                    MCP Clients
  Slack, WhatsApp, Telegram...      Web UI (Next.js)         Claude Desktop, Cursor
       |                                 |                        |
       v                                 v                        v
  Webhook Gateway ────────────────> API (FastAPI on GKE) <── MCP Server (SSE)
  per-user webhooks (whk_<ulid>)    |         |         |         |
  normalize to UniversalEnvelope    |         |         |         |
       |                            v         v         v         v
       v                       Supabase    Neo4j     GCS      Nango
  Webhook Pipeline             Postgres    Graphiti   raw      OAuth, tokens
  NATS + 40 typed agents       pgvector    temporal   binary   credentials
  classify -> analyze          BM25 FTS    knowledge  images   300+ providers
  embed -> extract entities         |      graph  |
       |                            |         |   |
       +------- results ----------->|         |   |
                                    v         v   v
                              Multi-Signal Search Engine
                              vector | fts | hybrid | graph | full
                                         |
                                    Reranker (RRF | MMR | cross-encoder)
                                         |
                                    RAG Chat with [1][2] citations
```

## Components

| Component | Stack | Namespace | Port | Deployment |
|-----------|-------|-----------|------|------------|
| **API** | Python 3.12, FastAPI, 70+ endpoints | `mem-dog` | 8080 | GKE |
| **UI** | Next.js 14, React 18, TypeScript | -- | 3000 | Cloud Run |
| **Webhook Pipeline** | Python 3.12, NATS JetStream, ADK | `webhook-pipeline` | 8080 | GKE |
| **Webhook Gateway** | Python 3.12, FastAPI, LiteLLM | `webhook-gateway` | 8080 | GKE |
| **Neo4j** | Neo4j 5.26 Community + Graphiti | `neo4j` | 7687 | GKE |
| **DigiMe Agent** | Node.js, OpenClaw runtime | `webhook-gateway` | 18789 | GKE |
| **Supabase** | Postgres 16 + pgvector, GoTrue, Kong | `supabase` | 5432 | GKE |
| **Nango** | OAuth, token refresh, credential encryption, 300+ providers | `nango` | 3003 | GKE |
| **MCP Server** | Python 3.12, FastMCP, SSE transport, 8 tools | `mem-dog` | 8080 | GKE |
| **Ollama** | gemma3 4b/12b/27b, embeddinggemma | `webhook-pipeline` | 11434 | GKE |

## Data Flow

### Ingestion

**Channel ingestion** (WhatsApp, Slack, Telegram, etc.):
1. Channel delivers message to **Webhook Gateway** via per-user webhook endpoint (`POST /webhooks/{webhook_id}`) or legacy channel path (`POST /webhooks/{channel_type}`)
2. Gateway resolves `user_id` from webhook record (new path) or identity heuristics (legacy), normalizes into `UniversalEnvelope` format
3. Gateway forwards to **API** via `POST /api/v1/ingest`
4. API stores raw data, creates tracing memory
5. API publishes to **Webhook Pipeline** via NATS
6. Pipeline runs 6-layer classification, routes to typed sub-agent
7. Sub-agent calls LLM, stores viewpoint + embedding + entities

**Direct ingestion** (UI upload or API call):
1. `POST /api/v1/data` stores content with metadata
2. Text content is also fed to Graphiti as an episode (fire-and-forget)
3. Optional: forward to pipeline for AI enrichment

### Knowledge Graph (dual-write)

Every entity extraction produces a dual-write:

1. Webhook pipeline extracts entities/relationships from data
2. `POST /api/v1/graph/entities/batch` writes to **Postgres** graph tables
3. Same data is written to **Graphiti/Neo4j** as a temporal episode
4. Graphiti performs its own LLM-powered entity resolution with temporal awareness
5. Facts get `valid_at`/`invalid_at` timestamps for point-in-time queries

### Search & Query

5 search modes, executed on demand:

| Mode | Engine | How it works |
|------|--------|-------------|
| **vector** | pgvector | Cosine similarity over embeddings |
| **fts** | Postgres tsvector | BM25 keyword matching |
| **hybrid** | pgvector + tsvector | Vector + BM25 merged with Reciprocal Rank Fusion |
| **graph** | Graphiti + Neo4j | BFS traversal + semantic search on knowledge graph |
| **full** | All | pgvector hybrid + Graphiti graph in parallel, RRF merged |

After retrieval, optional **reranking**: RRF, MMR (diversity), cross-encoder (LLM-scored).

For `graph` and `full` modes, optional **temporal filtering**: query facts valid at a specific point in time.

Results are passed to the **RAG Chat** endpoint which builds numbered context, calls the LLM, and returns answers with inline `[1][2]` citations.

## Storage

### Backends

Configured via `STORAGE_BACKEND` env var:

| Backend | Structured Data | Embeddings | Raw Binary | Use case |
|---------|----------------|------------|------------|----------|
| `local` | Filesystem (`~/.mem-dog`) | In-memory scan | Filesystem | Local dev |
| `gcs` | GCS buckets | GCS bucket | GCS bucket | Cloud (legacy) |
| `supabase` | `mem_dog_blobs` table | `mem_dog_embeddings` (pgvector) | GCS (`RAW_BUCKET`) | Production |

### Knowledge Graph Storage

| Store | What's stored | Required |
|-------|--------------|----------|
| **Postgres** (`mem_dog_entities`, `mem_dog_relationships`, `mem_dog_entity_data_mapping`) | Entities, relationships, entity-data mappings | Always (zero infra) |
| **Neo4j** (Graphiti) | Temporal episodes, entity nodes, fact edges with valid_at/invalid_at | Optional (`NEO4J_URI`) |

### Supabase Tables

| Table | Purpose |
|-------|---------|
| `mem_dog_blobs` | General blob store (metadata, memories, configs) |
| `mem_dog_embeddings` | pgvector embeddings + tsvector for BM25 |
| `mem_dog_entities` | Knowledge graph entities (8 types) |
| `mem_dog_relationships` | Directed entity relationships |
| `mem_dog_entity_data_mapping` | Entity-to-data-item links |
| `organizations` | Multi-tenant org hierarchy |
| `projects` | Projects within orgs |
| `org_members` | Org membership and roles |
| `agent_configs` | Per-agent pipeline configs |
| `webhooks` | Per-user webhook endpoints (whk_<ulid>) |
| `webhook_events` | Webhook event log for observability |

## AI / LLM Stack

### Model Tiers

| Tier | Default Model | Used for |
|------|--------------|----------|
| Small | gemma3:4b | JSON, CSV, YAML, XML, IoT |
| Medium | gemma3:12b | Code, email, chat, financial |
| Large | gemma3:27b | PDFs, Office docs, web pages |
| Multimodal | Qwen3-VL | Images, visual PDFs |
| Omni | Qwen3.5 | Audio, video |
| Embedding | embeddinggemma / gemini-embedding-001 | Vector embeddings |

### Fallback Chains

**Webhook pipeline**: Smart routing primary (Ollama Cloud) -> Gemini fallback -> self-hosted Ollama

**Chat with Data**: Local Ollama (15s timeout) -> Gemini fallback

**Graphiti**: Gemini (gemini-2.0-flash for LLM, gemini-embedding-001 for embeddings, Gemini reranker for cross-encoder)

### Classification

6-layer deterministic cascade (LLM is last resort):
1. Channel message detection
2. Source type field
3. Explicit data_type
4. Payload field heuristic
5. MIME registry
6. URL extension sniff
7. (fallback) LLM classifier (gemma3:4b)

## Networking (GKE)

External traffic enters through the `open-jaws` Gateway (L7 Global External Managed LB):

| Path | Destination | Timeout |
|------|-------------|---------|
| `/gke-api/*` | `api` service (prefix stripped) | 120s |
| `/oc/*` | `openclaw-node` (prefix stripped) | 30s |
| `/webhooks`, `/channels`, `/query`, `/chat`, etc. | `webhook-gateway` | 30s |

Internal service discovery: Kubernetes DNS (e.g. `api.mem-dog.svc.cluster.local:8080`, `neo4j.neo4j.svc.cluster.local:7687`).

## Security

| Layer | Implementation |
|-------|---------------|
| **Authentication** | Supabase Auth (email + Google OAuth) + per-user API keys (`md_*`) |
| **Authorization** | Per-item ACLs (private/shared/public/restricted) + `shared_with` |
| **Encryption** | Nango AES-256-GCM for integration credentials; Fernet AES-256 for AI provider API keys |
| **API Auth** | Dual-path: global API key OR per-user `md_<token>` OR JWT Bearer |
| **Gateway** | API key auth, IP allowlist, per-user webhook endpoints |
| **Data isolation** | `user_id` scoping on every table and query |

## Observability

| Feature | Implementation |
|---------|---------------|
| **Distributed tracing** | OpenTelemetry across all components, stored as `tracing` memories |
| **Metrics** | `http.server.request_count` counter (method/path/status) |
| **Token tracking** | Per-user, per-model, per-agent LLM token usage |
| **UI** | Insights dashboard + waterfall span viewer |
