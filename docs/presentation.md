# Mem-Dog: The Private AI System

**AI should be private. Not as a feature — as the foundation.**

---

## Slide 1 — The Problem

Every time you ask an AI a question, your data travels to a distant data center, gets processed on someone else's hardware, and a record of your query lives on infrastructure you'll never audit.

**For individuals:** Your personal thoughts, health records, financial details, and private conversations are one breach away from exposure. You pay per token, per seat, per month — and the bill scales with every question you ask.

**For enterprises:** Trade secrets, customer data, and proprietary research flow through third-party systems with opaque data-retention policies. Compliance teams can't audit what they don't control. A single vendor outage takes your AI offline.

**For developers:** You're stitching together a memory SDK here, an integration platform there, a vector database somewhere else, a knowledge graph from another vendor — and none of them talk to each other. Every new tool adds a new bill, a new API surface, and a new point of failure.

The AI industry has normalized this fragmentation. You get intelligence, but you surrender privacy. You get convenience, but you pay per token. You get capability, but you depend on someone else's uptime.

**We built Mem-Dog to end that trade-off.**

---

## Slide 2 — What is Mem-Dog?

A complete, self-hosted AI system that ingests data from 33 channel adapters and 300+ apps, enriches it with 42 specialized AI agents, stores it in a temporal knowledge graph, and makes it searchable through 5 search modes with RAG chat — all running on hardware you control.

Your laptop. A Mac Mini on your desk. A server rack in your office. A Kubernetes cluster in your cloud account. The AI never phones home because there's no home to phone.

### Four Pillars

| Pillar | What it means |
|--------|--------------|
| **Private by Design** | Data never leaves your network. No cloud dependency. No third-party data retention. Full offline/air-gapped capability. Zero trust boundaries in local mode. |
| **Fast Locally** | 6-layer deterministic classification routes data to the smallest capable model. Most queries finish in milliseconds on modest hardware. 80% of AI workload runs on the 4b model. |
| **Cost Efficient** | Local models on Ollama. Marginal cost per query = electricity. No per-token fees. No per-seat licensing. 60-80% cheaper than cloud-only at scale. $0/month on a Mac Mini. |
| **Genuinely Smart** | 42 agents, dual-layer knowledge graph, 5 search modes, 4 rerankers, RAG chat with citations, conversational agent across 33 messaging channels — all running locally. Gets smarter the more you use it. |

---

## Slide 3 — The Complete Platform

Mem-Dog is not a library, not a plugin, not a single-purpose tool. It's the full stack:

| Layer | What Mem-Dog provides | What others offer |
|-------|----------------------|-------------------|
| **Ingestion** | 33 channel adapters + 300+ app integrations (Nango) | Mem0: API-only. Zep: SDK-only. BerryDB: SDK-only. |
| **Enrichment** | 42 typed AI agents, 6-layer classification, 60+ data types | Mem0: fact extraction only. Dify: workflow builder. BerryDB: PDF/NER. |
| **Storage** | 10 memory types, versioned mutations, 3 backends, per-item ACLs | Mem0: 3 types. Zep: messages only. BerryDB: knowledge graph DB. |
| **Knowledge Graph** | Dual-layer Postgres + Graphiti/Neo4j with temporal reasoning | Zep: Graphiti only. Mem0: none. BerryDB: purpose-built. |
| **Search** | 5 modes (vector, FTS, hybrid, graph, full) + 4 rerankers | Mem0: vector only. Zep: semantic + graph. Snowflake: Cortex Search. |
| **Query** | RAG chat with inline `[1][2]` citations, memory-scoped | Dify: chat builder. Databricks: custom pipelines. Others: BYO. |
| **Agent** | DigiMe conversational AI in 25+ messaging apps | No equivalent in any competitor. |
| **AI Studio** | Search, Models, Routing, Agents, Infrastructure — all in one UI | No equivalent. |
| **UI** | Full web platform — dashboard, playground, telemetry, AI Studio, settings | Mem0: none. Zep: none. BerryDB: notebook UI. |
| **SDKs** | Python, TypeScript, Go, Rust, Ruby + LangChain/CrewAI/OpenAI/MCP adapters | Varies. |

---

## Slide 4 — Architecture

```
  300+ Apps (Nango)          Users
  Slack, WhatsApp,           Web UI (Next.js 14)
  Telegram, email...              |
       |                          v
       v                    ┌─────────────────┐
  Webhook Gateway           │  API (FastAPI)   │
  per-user endpoints        │  80+ endpoints   │
  33 channel adapters       │  Python 3.12     │
  normalize → Universal     └──┬──┬──┬──┬──────┘
  Envelope format              │  │  │  │
       │                       │  │  │  └──> Nango (300+ providers)
       v                       │  │  │       OAuth2, token refresh
  ┌────────────────┐           │  │  │       AES-256-GCM credentials
  │ Webhook Pipeline│          │  │  │
  │ NATS JetStream  │         │  │  └──> GCS (raw binary)
  │ 42 AI Agents    │         │  │
  │ classify → analyze│       │  └──> Neo4j + Graphiti
  │ embed → extract   │      │       temporal knowledge graph
  └────────┬───────────┘     │       valid_at / invalid_at
           │                  v
           │            Supabase (Postgres 16)
           │            ├── mem_dog_blobs (metadata)
           │            ├── mem_dog_embeddings (pgvector)
           │            ├── mem_dog_entities (8 types)
           │            ├── mem_dog_relationships
           │            ├── organizations / projects
           │            ├── webhooks / webhook_events
           │            └── agent_configs
           │                  │
           └── results ──────>│
                              v
                    ┌─────────────────────────┐
                    │  Multi-Signal Search     │
                    │  vector│fts│hybrid│graph│full│
                    │         +                │
                    │  Reranker (RRF│MMR│CE)   │
                    │         +                │
                    │  RAG Chat with [1][2]    │
                    └─────────────────────────┘
```

### Component Summary

| Component | Stack | Port | Deployment |
|-----------|-------|------|------------|
| **API** | Python 3.12, FastAPI, 33 routers, 80+ endpoints | 8080 | GKE (`memdog` namespace) |
| **UI** | Next.js 14, React 18, TypeScript | 3000 | Cloud Run |
| **Webhook Pipeline** | Python 3.12, NATS JetStream, ADK, 42 agents | 8080 | GKE (`webhook-pipeline`) |
| **Webhook Gateway** | Python 3.12, FastAPI, LiteLLM, 33 adapters | 8080 | GKE (`webhook-gateway`) |
| **DigiMe Agent** | Node.js, OpenClaw runtime, 4 skills | 18789 | GKE (`webhook-gateway`) |
| **MCP Server** | Python, SSE transport, 8 tools | 8091 | GKE (`memdog`) |
| **Neo4j** | Neo4j 5.26 Community + Graphiti | 7687 | GKE (`neo4j`) |
| **Supabase** | Postgres 16 + pgvector, GoTrue, Kong | 5432 | GKE (`supabase`) |
| **Nango** | OAuth, token refresh, 300+ providers | 3003 | GKE (`nango`) |
| **Ollama** | Gemma3 4b/12b/27b, embeddinggemma, Qwen3-VL | 11434 | GKE (`webhook-pipeline`) |
| **Redis** | Caching, rate limiting | 6379 | GKE |

**Single command to start everything:** `docker compose up` launches 11 services locally — UI, API, gateway, 3 Ollama tiers, Redis, PostgreSQL 16 + pgvector, Neo4j, MCP server, webhook processor.

---

## Slide 5 — Multi-Channel Ingestion

Data flows into Mem-Dog from three paths:

### Path 1: Channel Ingestion (33 channel adapters)

1. Channel delivers message to **Webhook Gateway** via per-user webhook endpoint (`POST /webhooks/{webhook_id}`)
2. Gateway resolves `user_id` from webhook record, normalizes into `UniversalEnvelope` format
3. Gateway forwards to **API** via `POST /api/v1/ingest`
4. API stores raw data, creates tracing memory
5. API publishes to **Webhook Pipeline** via NATS
6. Pipeline runs 6-layer classification, routes to typed sub-agent
7. Sub-agent calls LLM, stores viewpoint + embedding + entities

### Path 2: Direct Ingestion (UI or API)

1. `POST /api/v1/data` stores content with metadata
2. Text content is written to Graphiti as an episode (fire-and-forget)
3. Optional: forward to pipeline for AI enrichment

### Path 3: Conversational Ingestion (DigiMe)

1. User sends a message to DigiMe on WhatsApp, Signal, Telegram, etc.
2. DigiMe's `memdog-bridge` skill forwards every message to the webhook pipeline
3. DigiMe's `memdog-ingest` skill stores explicit data ("Remember my flight is at 3pm")
4. Channel identity resolution scopes all data to the correct user

### 33 Channel Adapters

| Native Adapters (33) | Bridge Channels via OpenClaw (15+) |
|-----------------------|------------------------------------|
| AppStore, Asana, Capterra, Datadog, Discord, Email, G2, Generic, GitHub, Google Business, Grafana, HubSpot, Jira, Linear, MS Teams, Notion, OpenClaw Bridge, OpsGenie, PagerDuty, Salesforce, Sentry, Slack, Stripe, Telegram, TripAdvisor, Trustpilot, Twilio, Video, Webchat, WhatsApp, Yelp, Zoom | Signal, Matrix, IRC, Google Chat, Line, Feishu, Mattermost, Nextcloud Talk, Nostr, Twitch, Zalo, BlueBubbles/iMessage, Synology Chat, and more |

### Per-User Webhook Endpoints

Every user gets their own webhook endpoints with unique IDs (`whk_<ulid>`):
- Create, manage, and monitor inbound webhooks
- HMAC secrets for payload verification
- Event logging for observability
- Stats tracking (delivery count, last event)

---

## Slide 6 — 42-Agent AI Enrichment Pipeline

Every piece of data that enters Mem-Dog goes through a multi-stage enrichment pipeline powered by 42 specialized AI agents.

### Processing Stages

```
Ingest → Stage (download) → Classify (6-layer) → Route → Analyze (LLM) → Viewpoint → Embedding → Entity Extraction → Graph Write
```

### 6-Layer Classification (LLM is the last resort)

| Layer | Method | Example |
|-------|--------|---------|
| 0 | URL not downloaded detection | URL → `url_download` agent first |
| 1 | Channel message detection | WhatsApp message → `channel_message` |
| 2 | Explicit `data_type` or `source_type` field | Direct classification from caller |
| 3 | Payload field heuristic | Has `latitude`/`longitude` → `gps` |
| 4 | MIME registry | `application/pdf` → `pdf` |
| 5 | URL extension sniff | `.csv` → `csv` |
| 6 | LLM classifier (fallback) | Gemma3:4b classifies ambiguous content |

Most data is classified deterministically in layers 0-5, avoiding LLM calls entirely — saving cost and latency.

### 42 Agent Types by Category

| Category | Agents | Examples |
|----------|--------|---------|
| **Documents** (5) | PDF, Office Doc, HTML Doc, Markdown, Web Page | Full text extraction, structure analysis |
| **Media** (5) | Image, Image Batch, Audio URL, Audio Stream, Video URL, Video Stream | Multimodal captioning, transcription |
| **Communication** (5) | Chat, Channel Message, Email, Feed, Calendar | Sentiment, intent, thread analysis |
| **Structured Data** (4) | JSON, CSV, YAML, XML | Schema inference, statistical summary |
| **Code & Logs** (3) | Code, Log File, Log Stream | Language detection, error classification |
| **Sensor & IoT** (4) | GPS, Biometric, IoT Sensor, Sensor | Time-series analysis, geofencing |
| **Spatial** (3) | Geospatial, LiDAR, 3D Model | Coordinate analysis, point cloud processing |
| **Specialized** (5) | Financial, Industrial, Infrastructure, Scientific, Satellite | Domain-specific entity extraction |
| **Binary** (3) | Binary Blob, Archive, Time Series | Format detection, content enumeration |
| **Medical** (1) | Medical Imaging | DICOM-aware processing |
| **Vehicle** (1) | Vehicle Telemetry | CAN bus, OBD-II analysis |
| **Conferencing** (1) | Conferencing | Meeting transcript analysis |
| **Download** (1) | URL Download | Fetch and stage remote content |

### Per-Agent Configuration

Each of the 42 agents is configurable per user:
- Custom system prompts
- Output schema overrides
- Model tier selection (small/medium/large/multimodal/omni)
- Processing flags (enable/disable per data type)
- Reusable skills and templates

---

## Slide 7 — AI Studio

AI Studio is Mem-Dog's unified control center for all AI capabilities, accessible as a top-level tab in the web UI.

### 5 Sub-Tabs

| Tab | What it does |
|-----|-------------|
| **Search & Chat** | RAG search with 5 modes and 4 rerankers. Viewpoint browser. Embedding manager. Conversational knowledge chat with inline `[1][2]` citations. |
| **Models** | Model Garden — connect 10+ AI providers (Ollama, Gemini, OpenAI, Anthropic, Groq, etc.). Encrypted API key storage. Model catalog discovery. Per-user provider configuration. |
| **Routing** | Smart Routing — per-agent-type model assignment. Primary and fallback chains. Visual routing table showing which model handles which data type. |
| **Agents** | Processing Flags (enable/disable AI processing per data type) + Agent Configs (custom prompts, schemas, model overrides for each of the 42 agent types). |
| **Infrastructure** | K8s Pod Management — create, scale (0-3 replicas), delete Ollama model pods from the browser. View logs, metrics, and status. Infrastructure pods shown read-only. |

### Model Garden — 10+ AI Providers

| Provider | Type | Notes |
|----------|------|-------|
| **Ollama** | Local | Self-hosted, free inference, GPU-accelerated |
| **Ollama Cloud** | Managed | Hosted Ollama, pay-per-use |
| **Google Gemini** | Cloud | gemini-2.5-flash, embedding-001, reranker |
| **OpenAI** | Cloud | GPT-4o, GPT-4o-mini, o1, o3-mini, embeddings |
| **Anthropic** | Cloud | Claude 4, Sonnet, Haiku |
| **Groq** | Cloud | Ultra-fast inference |
| **Mistral** | Cloud | Open-weight models |
| **Cohere** | Cloud | Command, Embed, Rerank |
| **DeepSeek** | Cloud | DeepSeek-V3, R1 |
| **xAI** | Cloud | Grok 4, Grok 3 models |
| **OpenRouter** | Aggregator | Routes to 100+ models |
| **Together AI** | Cloud | Open-source model hosting |
| **HuggingFace** | Cloud/Local | Model hub inference |
| **AWS Bedrock** | Cloud | Enterprise models |
| **vLLM** | Self-hosted | High-throughput serving |
| **LiteLLM** | Proxy | Unified API for any provider |

### 5-Tier Smart Routing

Data is automatically routed to the smallest model that can handle it well:

| Tier | Default Model | Used for | Cost |
|------|--------------|----------|------|
| **Small** | Gemma3:4b | JSON, CSV, YAML, XML, IoT, simple text | Free (local) |
| **Medium** | Gemma3:12b | Code, email, chat, financial data | Free (local) |
| **Large** | Gemma3:27b | PDFs, Office docs, web pages, complex documents | Free (local) |
| **Multimodal** | Qwen3-VL | Images, visual PDFs, screenshots | Free (local) |
| **Omni** | Qwen3.5 | Audio, video, multi-format | Free (local) |
| **Embedding** | embeddinggemma / gemini-embedding-001 | Vector embeddings for search | Free (local) or cloud |

### Fallback Chains

If a local model is unavailable or overloaded, the system gracefully falls back:

- **Webhook pipeline:** User's configured engine → Ollama Cloud → Gemini → self-hosted Ollama
- **Chat with Data:** Local Ollama (15s timeout) → Gemini fallback
- **Graphiti:** Gemini (gemini-2.0-flash for LLM, gemini-embedding-001 for embeddings)

### Infrastructure Pod Management

The Infrastructure tab lets you manage Ollama model deployments directly from the browser:

- **Create pods** — name, tier (small/medium/large), models to preload, replicas
- **Scale** — 0 to 3 replicas with one click (wake/sleep)
- **Monitor** — status badges (running/pending/scaled_to_zero), CPU/memory metrics, logs viewer
- **Managed vs Infrastructure** — pods created via UI are "managed" (full control); pre-existing pods show as "infrastructure" (read-only, visible for monitoring)

All managed pods are prefixed `mdl-` and labelled `memdog/managed-model=true`. K8s RBAC restricts the API service account to the `webhook-pipeline` namespace.

---

## Slide 8 — Temporal Knowledge Graph

Mem-Dog maintains a **dual-layer knowledge graph** that tracks entities, relationships, and how facts change over time.

### Layer 1: Postgres (Always Active, Zero Infrastructure)

| Table | Contents |
|-------|----------|
| `mem_dog_entities` | 8 entity types: person, organization, product, location, date, URL, concept, event |
| `mem_dog_relationships` | Directed relationships between entities (e.g., "works_at", "located_in") |
| `mem_dog_entity_data_mapping` | Links entities back to the source data items they were extracted from |

- Deduplicated via canonical form unique index
- No additional infrastructure — uses the same Postgres that stores everything else
- Queryable via `/api/v1/graph/entities` and `/api/v1/graph/relationships`

### Layer 2: Graphiti + Neo4j (Optional, Temporal)

When `NEO4J_URI` is configured, Mem-Dog enables temporal knowledge graph capabilities powered by [Graphiti](https://github.com/getzep/graphiti) (Zep's open-source Apache 2.0 engine):

- **Temporal facts:** Every fact gets `valid_at` and `invalid_at` timestamps
- **Point-in-time queries:** "Who was the CEO of Acme Corp on June 1, 2025?"
- **Automatic entity resolution:** Graphiti uses LLM-powered deduplication to merge "John Smith", "J. Smith", and "John" into a single entity node
- **Community detection:** Label propagation identifies clusters of related entities
- **Fire-and-forget dual-write:** API writes to both Postgres and Graphiti on every entity extraction

### How the Dual-Write Works

```
Webhook Pipeline extracts entities/relationships
    │
    ├──> POST /api/v1/graph/entities/batch  ──> Postgres (instant)
    │
    └──> Graphiti episode ingestion          ──> Neo4j (async, LLM-powered)
              │
              ├── Entity resolution (merge duplicates)
              ├── Fact extraction (with temporal bounds)
              └── Community detection (cluster related entities)
```

### Entity-Aware RAG

When a user searches, the system:
1. Matches query terms against known entities
2. Performs BFS traversal on the graph to find related entities
3. Injects entity context into the LLM system prompt
4. Returns answers enriched with structured knowledge, not just raw text chunks

---

## Slide 9 — 5 Search Modes + 4 Rerankers

Mem-Dog provides the most comprehensive search pipeline of any AI memory platform.

### Search Modes

| Mode | Engine | How it works | Best for |
|------|--------|-------------|----------|
| **vector** | pgvector | Cosine similarity over embeddings | Semantic meaning ("things like this") |
| **fts** | Postgres tsvector | BM25 keyword matching | Exact terms, names, IDs |
| **hybrid** | pgvector + tsvector | Vector + BM25 merged with Reciprocal Rank Fusion | General purpose (default) |
| **graph** | Graphiti + Neo4j | BFS traversal + semantic search on the knowledge graph | Entity relationships, temporal facts |
| **full** | All engines | pgvector hybrid + Graphiti graph in parallel, RRF merged | Maximum recall, cross-signal discovery |

### Reranking Strategies

| Reranker | Method | When to use |
|----------|--------|-------------|
| **None** | Raw scores from search engine | Fast, good enough for simple queries |
| **RRF** | Reciprocal Rank Fusion | Merging results from multiple search modes |
| **MMR** | Maximal Marginal Relevance | When you want diverse results, not just the top-N most similar |
| **Cross-encoder** | LLM-scored relevance | Highest accuracy, uses model server to re-score each result |

### Temporal Filtering

For `graph` and `full` modes, add temporal constraints:
- "Who was CEO in 2024?" → filters facts by `valid_at <= 2024 AND invalid_at > 2024`
- "What changed about the product roadmap since January?" → temporal range query

### RAG Chat with Citations

The `/api/v1/ai/query/chat` endpoint provides conversational answers:
1. Runs the selected search mode to retrieve relevant data
2. Applies reranking strategy
3. Builds numbered context from results
4. Calls LLM with context + conversation history
5. Returns answer with inline `[1]`, `[2]`, `[3]` citation markers linking back to source data
6. Supports memory scoping — restrict search to specific memory types or time ranges

---

## Slide 10 — Memory System

Mem-Dog's memory system is designed for diverse data lifecycles — from ephemeral conversation context to permanent organizational knowledge.

### 10 Memory Types in 4 Categories

| Category | Type | Default TTL | Purpose |
|----------|------|-------------|---------|
| **Conversation** | `conversation` | 1 hour | Multi-turn dialogue context |
| **Session** | `session` | 24 hours | Bounded interaction state |
| | `timeline` | 7 days | Chronological activity log |
| | `tracing` | 3 days | OpenTelemetry distributed traces |
| **User** | `user` | Never | Profile facts, preferences |
| | `factual` | Never | Verified, canonical facts |
| | `episodic` | Temporary | Event-based memories |
| | `semantic` | Never | Conceptual knowledge, abstractions |
| | `custom` | Varies | User-defined memory types |
| **Organizational** | `organizational` | Never | Org-level facts, policies, decisions |

### Memory Features

| Feature | Details |
|---------|---------|
| **Versioning** | Every mutation creates a new version with diff tracking. Full history retrievable. |
| **Access control** | 4 levels: private (default), shared, public, restricted. Fine-grained `shared_with` user list for shared/restricted. |
| **TTL & expiry** | Default TTL per type. Override with `ttl_hours` or `no_expiry=true`. Automatic cleanup. |
| **LLM compression** | Summarize verbose conversation memories into structured summaries. Archive originals. Keep key facts, entities, action items. Auto-triggers at configurable thresholds. |
| **Project scoping** | Memories linked to organization/project hierarchy for multi-tenant isolation. |
| **ID format** | `mem_<type>_<ulid>` — e.g., `mem_conv_01JQXYZ`, `mem_user_01JQABC` |

---

## Slide 11 — DigiMe: Your Personal AI Assistant

DigiMe is an AI agent that lives inside your messaging apps — turning any chat platform into a window to your entire knowledge base.

### How It Works

```
User (WhatsApp/Telegram/Slack/Signal/Discord/...)
    │
    └──> "What did we discuss about the product launch?"
              │
              v
         OpenClaw Runtime (DigiMe)
              │
              ├── memdog-bridge skill    → Forward ALL messages to pipeline
              ├── memdog-query skill     → Lookup memories and data
              ├── memdog-semantic-search  → Vector search across all data
              └── memdog-ingest skill    → Store new data from conversation
              │
              v
         "Based on your meetings [1] and Slack messages [2],
          the product launch is scheduled for Q3. Action items
          include finalizing the pricing model and..."
```

### Multi-User Data Isolation

DigiMe supports multiple users on a single instance with complete data isolation:

```
User A (WhatsApp, +1925...)  ──> channel identity resolution
                                  (whatsapp, +1925...) → user_id_A
                                  All queries scoped to user_id_A

User B (Signal, signal_id)   ──> channel identity resolution
                                  (signal, signal_id) → user_id_B
                                  All queries scoped to user_id_B
```

User A cannot see User B's data, and vice versa — enforced at the API level.

### 4 Skills

| Skill | Purpose | Behavior |
|-------|---------|----------|
| **memdog-bridge** | Record everything | Forwards EVERY incoming message to the webhook pipeline. Non-negotiable. |
| **memdog-ingest** | Store explicit data | Stores notes, facts, session memories via `POST /api/v1/data` |
| **memdog-query** | Lookup data | Retrieves memories, data items, lists via API |
| **memdog-semantic-search** | Recall by meaning | Vector similarity search via `POST /api/v1/ai/query/semantic` |

### Supported Platforms (25+)

WhatsApp, Telegram, Signal, Slack, Discord, Matrix, MS Teams, IRC, Google Chat, Line, Feishu, Mattermost, Nextcloud Talk, Nostr, Twitch, Zalo, BlueBubbles/iMessage, Synology Chat, Rocket.Chat, WeChat, Viber, Webchat, and more.

---

## Slide 12 — Integration Platform (Nango-Powered)

Mem-Dog's integration layer is powered by [Nango](https://www.nango.dev/) (self-hosted), providing enterprise-grade connectivity to 300+ applications.

### What Nango Provides

| Capability | Details |
|------------|---------|
| **300+ provider templates** | Community-maintained OAuth flows, API schemas, and webhook configs |
| **OAuth2 flows** | Full authorization code grant, PKCE, state management, consent screens |
| **Automatic token refresh** | No background tasks, no 401 retry logic — Nango handles it transparently |
| **Credential encryption** | AES-256-GCM with `NANGO_ENCRYPTION_KEY` |
| **Per-user connections** | Each connection tagged with `end_user_id` for multi-tenant isolation |

### What Mem-Dog Adds On Top

| Capability | Details |
|------------|---------|
| **Per-user webhook endpoints** | `whk_<ulid>` — create, manage, monitor inbound webhooks with HMAC secrets and event logging |
| **Channel normalization** | 33 adapters convert platform-specific formats into `UniversalEnvelope` |
| **AI enrichment** | 42 specialized agents process every piece of ingested data |
| **Knowledge graph** | Entities and relationships extracted and dual-written to Postgres + Graphiti |
| **Multi-signal search** | 5 search modes across all integrated data |
| **Credential-injecting proxy** | `POST /proxy/{provider}/{path}` — make authenticated API calls to any connected service without exposing tokens |
| **Response normalization** | `?normalize=contact|calendar_event` — standardize responses across providers |
| **Google Drive push** | Write back to Google Drive via dedicated router |
| **Gmail push** | Write back to Gmail via dedicated router |
| **Zoom WebSocket** | Real-time Zoom event streaming |

### Integration Categories

CRM, email, messaging, project management, cloud storage, social media, developer tools, analytics, e-commerce, payments, HR, accounting, marketing, support, and more.

---

## Slide 13 — Web UI

A full-featured web platform built with Next.js 14, React 18, and TypeScript. Dark-mode glassmorphism design with Tailwind CSS.

### 5 Sidebar Sections

| Section | Tabs | What they do |
|---------|------|-------------|
| **Knowledge** | Data, Memories | Browse all ingested data with metadata. Manage memories across 10 types with TTL, access control, and versioning. |
| **AI Studio** | Search & Chat, Models, Routing, Agents, Infrastructure | Unified AI control center — semantic search, model management, smart routing, agent configuration, K8s pod management. |
| **Monitor** | Insights, Telemetry | Stats dashboard (data counts, embeddings, agent performance). OpenTelemetry waterfall trace viewer for distributed tracing. |
| **Develop** | Playground | 4 sub-tabs: **Channel Simulator** (test webhooks across 33 channels), **Data Insert** (6 upload modes), **Knowledge Chat** (RAG chat with all 5 search modes), **MCP** (test MCP tools). |
| **Settings** | Profile, Organizations, Apps, Webhooks, API Keys | User profile, org/project hierarchy, Nango integrations, webhook management, API key generation. |

### Interactive Playground

The playground is a developer sandbox for testing the full pipeline:

- **Channel Simulator:** Select a channel type (WhatsApp, Slack, Discord, etc.), compose a message, send it through the webhook gateway, and watch it flow through classification → enrichment → storage
- **6-Mode Upload:** Text/dictation, file upload, URL fetch, camera capture, voice recording, video recording
- **Knowledge Chat:** Conversational RAG interface with search mode selector, reranker selector, memory type scoping, and inline citation display
- **MCP Playground:** Test the 8 MCP tools interactively for Claude Desktop/Cursor integration

---

## Slide 14 — Developer Experience

### 5 Language SDKs

| Language | Implementation | Features |
|----------|---------------|----------|
| **Python** | httpx, async support | Full client (70+ methods) + Simple facade (8 methods) + Agent adapters |
| **TypeScript** | Native fetch | Full API coverage, type-safe |
| **Go** | stdlib net/http | Idiomatic Go, no external dependencies |
| **Rust** | async tokio + reqwest | Fully async, zero-cost abstractions |
| **Ruby** | native HTTP | Clean Ruby interface |

### Simple SDK — 8 Methods, Full Power

```python
from mem_dog_client import MemDog

m = MemDog("http://localhost:8080", api_key="md_...", user_id="user1")

# Ingest
m.add("Meeting notes from standup", tags=["standup"], memory_type="session")

# Search (all 5 modes)
results = m.search("what happened in standup?", use_ai=True)

# Knowledge graph
entities = m.entities("Google")

# Retrieve & manage
item = m.get("data_01ABC...")
m.delete("data_01ABC...")

# LLM compression
m.compress("mem_session_xyz", archive_originals=True)

# Related items
related = m.related("data_01ABC...")
```

### Agent Framework Adapters

| Framework | Adapter | What it does |
|-----------|---------|-------------|
| **LangChain** | `ChatMessageHistory` + `Retriever` | Drop-in memory and retrieval for LangChain chains |
| **CrewAI** | `save/search` | Persistent memory for CrewAI agents |
| **OpenAI** | Function calling | Mem-Dog as an OpenAI function tool |
| **MCP** | Model Context Protocol | 8 tools for Claude Desktop, Cursor, and any MCP-compatible client |

### MCP Server — 8 Tools

| Tool | What it does |
|------|-------------|
| `mem_dog_add` | Store new data with tags and metadata |
| `mem_dog_search` | Semantic search with mode selection |
| `mem_dog_get` | Retrieve a specific data item |
| `mem_dog_list` | List data with filters |
| `mem_dog_delete` | Delete data |
| `mem_dog_entities` | Query knowledge graph entities |
| `mem_dog_memories` | List and manage memories |
| `mem_dog_chat` | RAG chat with citations |

### 80+ REST Endpoints

Full OpenAPI spec at `localhost:8080/docs`. Key endpoint groups:

| Group | Endpoints | Examples |
|-------|-----------|---------|
| **Data** | CRUD, versions, batch | `POST /data`, `GET /data/{id}`, `GET /data/{id}/versions` |
| **Memory** | All 10 types, TTL, ACLs | `POST /memories`, `GET /memories`, `POST /memories/{id}/compress` |
| **Search** | 5 modes, 4 rerankers | `POST /ai/query/semantic`, `POST /ai/query/chat` |
| **Graph** | Entities, relationships, facts | `POST /graph/entities/batch`, `GET /graph/facts` |
| **AI** | Embeddings, viewpoints, models | `POST /ai/embeddings`, `GET /ai/models` |
| **K8s Pods** | Create, scale, delete model pods | `POST /models/k8s-pods`, `PATCH /models/k8s-pods/{name}/scale` |
| **Integrations** | Nango proxy, connections | `GET /integrations/providers`, `POST /proxy/{provider}/{path}` |
| **Webhooks** | Per-user endpoints | `POST /webhooks`, `GET /webhooks/{id}/events` |
| **Orgs** | Multi-tenant hierarchy | `POST /orgs`, `POST /orgs/{id}/projects` |
| **Push** | Write-back to services | `POST /gdrive/push`, `POST /gmail/push`, `POST /zoom/push` |

---

## Slide 15 — Organizations & Multi-Tenancy

Mem-Dog supports full multi-tenant organization hierarchies for teams and enterprises.

### Hierarchy

```
Organization (team or company)
    │   org_<ulid>
    │   roles: owner, admin, member, viewer
    │
    ├── Project A (app or workspace)
    │       proj_<ulid>
    │       ├── Data items (scoped)
    │       ├── Memories (scoped)
    │       ├── Embeddings (scoped)
    │       └── Agent configs (scoped)
    │
    └── Project B
            proj_<ulid>
            └── ...
```

### Capabilities

- **Role-based access:** owner, admin, member, viewer — each with appropriate permissions
- **Project scoping:** Pass `?project_id=` to any data, memory, or embedding query to scope results
- **Data isolation:** All queries are scoped by `user_id` at the database level
- **Per-item ACLs:** private (default), shared, public, restricted — with `shared_with` user list
- **Backfill support:** Default org + project created for existing data migration

---

## Slide 16 — Security & Observability

### Security Layers

| Layer | Implementation |
|-------|---------------|
| **Authentication** | Supabase Auth (email + Google OAuth) via GoTrue |
| **API Keys** | Per-user keys (`md_<token>`, 44 chars) with O(1) Supabase lookup |
| **JWT** | Supabase JWT (`sub` claim), auto-creates user profile on first login |
| **Credential Encryption** | Nango: AES-256-GCM for integration credentials. Fernet: AES-256 for AI provider API keys. |
| **Data Isolation** | `user_id` scoping on every table and query — no cross-tenant data leakage |
| **Access Control** | 4 levels (private/shared/public/restricted) + `shared_with` user list per item |
| **Gateway Security** | API key auth, IP allowlist, rate limiting, per-user webhook endpoints |
| **Webhook Verification** | HMAC secrets per webhook endpoint for payload integrity |
| **K8s RBAC** | Model pod management restricted to `webhook-pipeline` namespace via Role/RoleBinding |

### Observability

| Feature | Implementation |
|---------|---------------|
| **Distributed Tracing** | OpenTelemetry across all components (API, pipeline, gateway), stored as `tracing` memories |
| **Waterfall UI** | Visual span viewer in the Telemetry tab — trace a request from ingestion through classification, enrichment, embedding, and graph write |
| **Metrics** | `http.server.request_count` counter by method, path, and status code |
| **Token Tracking** | Per-user, per-model, per-agent LLM token usage tracking |
| **Insights Dashboard** | Data counts, embedding stats, memory stats, agent performance metrics |
| **Version History** | Every data mutation creates a new version with diff tracking |
| **Webhook Events** | Event log per webhook endpoint — delivery count, last event, error tracking |
| **Pod Metrics** | CPU/memory usage for Ollama pods via K8s metrics API |

---

## Slide 17 — Data Privacy

### Zero Trust Boundaries (Local Mode)

```
memdog privacy stack:

  User (WhatsApp/Signal/Slack)
    ↓ encrypted channel (Signal E2E, etc.)
  OpenClaw Node / DigiMe (your pod)
    ↓ cluster-internal HTTP
  Webhook Gateway (your pod, identity resolution)
    ↓ cluster-internal HTTP
  42 AI Agents + Ollama (your pod, LOCAL model)
    ↓ no network call
  Postgres + Neo4j (your pod, your disk)
    ↓ encrypted at rest (your keys)
  Search/RAG (your pod, local pgvector)

  Data never leaves your infrastructure.
  Zero third-party API calls in full local mode.
  Third parties who see your data: 0.
```

### Privacy Scenarios

| Scenario | How Mem-Dog helps |
|----------|-------------------|
| **Healthcare (HIPAA)** | Run on Mac Mini in clinic. Patient data never leaves building. Local Ollama processes notes. |
| **Legal (privilege)** | Attorney-client data processed locally. No third party ever sees content. |
| **Corporate IP** | Product roadmaps, financials in local Postgres. 42-agent pipeline classifies without external calls. |
| **EU data (GDPR)** | Host in Germany. Data residency by physics. Right to erasure = DELETE from your Postgres. Provable. |
| **Air-gapped** | Full stack runs without internet. Ollama, Postgres, Neo4j — all local. |

---

## Slide 18 — Use Cases

### Core Use Cases

| Use Case | How Mem-Dog Helps |
|----------|-------------------|
| **Personal Knowledge Base** | Capture from WhatsApp, email, Slack. Semantic search across everything. Never lose a conversation or idea. DigiMe lets you query from any messaging app. |
| **Team Memory** | Shared organizational memory across channels. Auto-classify meetings, decisions, action items. Queryable by anyone on the team. |
| **Customer Intelligence** | Ingest support tickets, CRM, chat logs. AI extracts sentiment and trends. 300+ app connections via Nango. Knowledge graph links customers to products and issues. |
| **Research & Analysis** | Ingest PDFs, papers, web pages, datasets. AI viewpoints and summaries. Semantic connections across sources. Temporal graph tracks evolving findings. |
| **Compliance & Audit** | Every mutation versioned. OpenTelemetry tracing. Per-item ACLs. Immutable audit trail. Role-based org hierarchy. |
| **IoT & Sensor Data** | GPS, biometric, weather, industrial sensors. Specialized agents for time-series and geospatial data. Real-time ingestion via webhooks. |

### Industry-Specific Use Cases

| Use Case | How Mem-Dog Helps |
|----------|-------------------|
| **Legal & Contract Intelligence** | Ingest contracts, NDAs, legal briefs. AI extracts clauses, obligations, deadlines. Temporal graph tracks amendments over time. |
| **Healthcare & Clinical Notes** | Process medical records, imaging reports, lab results. DICOM-aware agents. Knowledge graph links patients, conditions, treatments. |
| **Education & Training** | Ingest lectures, textbooks, course materials. AI generates study guides. Students query their learning history across all materials. |
| **Sales Enablement** | Connect Salesforce, HubSpot, email. AI summarizes deal history, extracts action items. Search across all customer touchpoints. |
| **Media Monitoring** | RSS feeds, social media, news APIs. Real-time sentiment analysis. Track brand mentions across channels with temporal trends. |
| **Meeting Intelligence** | Zoom, Teams, Google Meet recordings. AI transcribes, extracts decisions, action items. Searchable meeting memory across your org. |
| **Knowledge Management** | Connect Notion, Confluence, Google Docs. AI indexes and cross-references documentation. Ask questions across all your wikis. |

---

## Slide 19 — Cost Advantage

Cloud AI bills grow linearly with usage — every token, every seat, every month.

### Cost Comparison (10,000 items/month)

| Cost Category | Mem-Dog (Mac Mini) | Mem-Dog (GKE) | Cloud-Only (SaaS) |
|---------------|-------------------|---------------|-------------------|
| **LLM inference** | $0 (local Ollama) | $15-50 (Gemini) | ~$160/mo (API) |
| **Embeddings** | $0 (local embeddinggemma) | $5-15 (API) | ~$20/mo |
| **Platform fee** | $0 | $0 | $99+/mo |
| **Infrastructure** | $0 (one-time hardware) | ~$150-300/mo (GKE) | Included |
| **Per-seat fee** | $0 | $0 | Per-user pricing |
| **Total** | **$0/month** | **$170-365/month** | **$280-500+/month** |

### Why Mem-Dog is 60-80% Cheaper at Scale

1. **6-layer deterministic classification** — avoids LLM calls for type detection
2. **Default small model (Gemma3:4b)** — ~80% of data processes on the smallest, fastest local model
3. **5-tier smart routing** — simple data stays on small models; only complex content escalates
4. **Local embeddings** — embeddinggemma, no embedding API costs
5. **No per-seat licensing** — one deployment serves your entire team
6. **Predictable costs** — infrastructure cost is fixed, not proportional to query volume

### Hardware Recommendations

| Mac Mini Model | RAM | Profile | Monthly Cost | What you get |
|---------------|-----|---------|-------------|-------------|
| M2 16GB | 16 GB | standard | $0 | Full stack, cloud LLMs (Gemini) |
| M4 Pro 48GB | 48 GB | full | $0 | Everything + local gemma3:4b + embeddings |
| M4 Pro/Max 64GB | 64 GB | full | $0 | Everything + all Ollama models incl. 27b |

### Pre-flight Resource Check

```bash
./scripts/preflight-check.sh                    # Check local resources
./scripts/preflight-check.sh --profile standard  # Specific profile
./scripts/preflight-check.sh --gke               # Check GKE cluster capacity
```

---

## Slide 20 — How Mem-Dog Compares

### Feature Matrix

|  | Mem-Dog | Mem0 | Zep | BerryDB | Snowflake | Databricks |
|--|---------|------|-----|---------|-----------|------------|
| **Self-hosted / air-gapped** | Yes | No | No | No | No | No |
| **Local AI models ($0)** | Yes | No | No | No | No | No |
| **33 channel adapters** | Yes | No | No | No | No | No |
| **300+ app integrations** | Yes | No | No | No | Partial | Partial |
| **42 specialized AI agents** | Yes | No | No | No | No | No |
| **Temporal knowledge graph** | Yes | No | Yes | Yes | No | No |
| **5 search modes + 4 rerankers** | Yes | Partial | Partial | Partial | Partial | No |
| **RAG chat with citations** | Yes | Partial | Partial | Yes | Yes | Custom |
| **10 memory types with TTL** | Yes | Partial | No | No | No | No |
| **Conversational agent (DigiMe)** | Yes | No | No | No | No | No |
| **AI Studio (unified UI)** | Yes | No | No | Partial | No | Partial |
| **K8s pod management UI** | Yes | No | No | No | No | No |
| **MCP server for AI IDEs** | Yes | No | No | No | No | No |
| **Multi-language SDKs (5)** | Yes | Partial | No | Partial | Yes | Yes |
| **Petabyte-scale analytics** | No | No | No | No | Yes | Yes |
| **ML model training** | No | No | No | Partial | Partial | Yes |
| **Enterprise compliance certs** | DIY | No | No | No | Yes | Yes |

### Positioning

- **Mem0** (49.8k stars, $24M Series A) is a memory SDK — adds memory to your app. Mem-Dog is the entire app.
- **Zep** is a context engine with Graphiti — tracks facts. Mem-Dog integrates Graphiti AND adds 33 channel adapters, 42 agents, 5 search modes, and a full UI.
- **BerryDB** is a multi-modal knowledge DB — stores and searches data. Mem-Dog adds real-time channel ingestion, auto-enrichment, DigiMe agent, and self-hosting.
- **Snowflake** is an enterprise data warehouse — petabyte SQL analytics. Mem-Dog serves a different market: private AI memory for individuals and small teams.
- **Databricks** is an enterprise data lakehouse — ML training at scale. Mem-Dog focuses on ingestion, enrichment, and retrieval, not model training.
- **Nango** is an integration platform — connects your apps. Mem-Dog uses Nango as a backend AND adds AI enrichment, knowledge graph, and search on top.
- **Dify.ai** is a workflow builder — design AI pipelines. Mem-Dog ships 42 pre-built agents with 6-layer routing out of the box.

---

## Slide 21 — Deployment Options

### Three Paths

| Option | What you get | Best for |
|--------|-------------|----------|
| **Local (Docker Compose)** | `docker compose up` — 11 services, hot-reload, local storage, self-hosted Ollama, Neo4j. No cloud needed. | Development, evaluation, personal use |
| **Google Cloud (GKE + Cloud Run)** | Production-grade: API + pipeline + gateway on GKE, UI on Cloud Run, Supabase with pgvector, Nango, Neo4j, L7 gateway. | Teams, production workloads |
| **Mac Mini Home Server** | Full production stack on Apple Silicon. Native GPU for Ollama. Complete data sovereignty. | Privacy-first individuals and small teams |

### GKE Namespace Layout

| Namespace | Services |
|-----------|----------|
| `memdog` | API, MCP Server |
| `webhook-pipeline` | NATS worker, 42 agents, Ollama (3 tiers) |
| `webhook-gateway` | Webhook Gateway, DigiMe (OpenClaw Node) |
| `supabase` | Postgres 16 + pgvector, GoTrue, Kong, PostgREST, Realtime, Meta, Studio |
| `neo4j` | Neo4j 5.26 Community |
| `nango` | Nango Server + Nango Postgres |

### Deploy Commands

```bash
# Local — everything in one command
docker compose up

# Pre-flight check
./scripts/preflight-check.sh --profile full

# GKE — per-component deployment
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-api-gke -p memdog-dev -e dev

./scripts/manual-deploy.sh deploy-ui -p memdog-dev -e dev
```

---

## Slide 22 — By the Numbers

| Metric | Value |
|--------|-------|
| **AI Agents** | 42 specialized sub-agents |
| **Data Types** | 60+ (media, documents, code, comms, sensors, spatial, binary, medical, legal, financial, satellite, vehicle, infrastructure) |
| **Channel Adapters** | 33 native + 15+ via OpenClaw bridge |
| **App Integrations** | 300+ via Nango |
| **Search Modes** | 5 (vector, FTS, hybrid, graph, full) |
| **Rerankers** | 4 (none, RRF, MMR, cross-encoder) |
| **Memory Types** | 10 across 4 categories |
| **AI Providers** | 16+ (Model Garden) |
| **Language SDKs** | 5 (Python, TypeScript, Go, Rust, Ruby) |
| **API Routers** | 33 |
| **REST Endpoints** | 80+ |
| **MCP Tools** | 8 |
| **Entity Types** | 8 (person, org, product, location, date, URL, concept, event) |
| **Classification Layers** | 6 deterministic + 1 LLM fallback |
| **Model Tiers** | 5 (small → medium → large → multimodal → omni) |
| **Docker Services** | 11 (single `docker compose up`) |
| **K8s Namespaces** | 6 (memdog, webhook-pipeline, webhook-gateway, supabase, neo4j, nango) |
| **Cost (self-hosted)** | $0/month recurring |
| **Cost Savings** | 60-80% vs. cloud-only at scale |
| **Startup Time** | ~30 seconds (`docker compose up`) |

---

## Slide 23 — Summary

### The Private AI System

Mem-Dog is the only platform that combines all of these in a single, self-hosted system:

**Ingest** from 33 channel adapters and 300+ apps.
**Enrich** with 42 specialized AI agents across 60+ data types.
**Store** with 10 memory types, versioning, TTL, and per-item access control.
**Graph** entities and relationships in a dual-layer temporal knowledge graph.
**Search** with 5 modes, 4 rerankers, and temporal fact queries.
**Query** with RAG chat and inline citations.
**Manage** models, routing, agents, and infrastructure from AI Studio.
**Connect** via 5 language SDKs, 8 MCP tools, agent framework adapters, and 80+ REST endpoints.
**Monitor** with OpenTelemetry distributed tracing and insights dashboards.
**Converse** through DigiMe in 25+ messaging platforms.

Private by design. Fast locally. Cost efficient. Genuinely smart.

> **Your AI. Your hardware. Your rules.**
