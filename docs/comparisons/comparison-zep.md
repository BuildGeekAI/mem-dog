# mem-dog vs Zep: Detailed Comparison

**Last updated:** March 2026

Zep is a context engineering platform built on temporal knowledge graphs (open-source Graphiti engine). It assembles personalized context from user conversations and business data for AI agents. This document compares mem-dog against Zep feature-by-feature.

---

## At a Glance

| | mem-dog | Zep |
|-|---------|-----|
| **What it is** | Private AI system with multi-channel ingestion, AI pipeline, and query engine | Context engineering platform built on temporal knowledge graphs |
| **Focus** | End-to-end data lifecycle: ingest, enrich, store, query | Assembling personalized context for AI agents from conversations and business data |
| **Deployment** | Self-hosted only (Docker, GKE, Mac Mini) | Zep Cloud (managed) + self-hosted |
| **License** | Proprietary | Open-source (Graphiti) + proprietary cloud |
| **Pricing** | Free (self-hosted) | Free tier → paid tiers → Enterprise |
| **Core engine** | 40-agent webhook pipeline + pgvector + Postgres graph | Temporal knowledge graph (Graphiti) with episodic/entity nodes |

---

## Feature-by-Feature Comparison

### Data Ingestion

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Multi-channel ingestion** | 25+ channels (WhatsApp, Telegram, Slack, Discord, Signal, email, etc.) via DigiMe agent | None — SDK-only ingestion |
| **Web UI upload** | 6 modes: text, file, URL, camera, voice, video | None |
| **Webhook pipeline** | Real-time NATS streaming with typed message routing | None |
| **Integration platform** | 300+ providers with OAuth2, API-key auth, encrypted credentials | None |
| **Chat message ingestion** | Via webhook pipeline or API | First-class: `memory.add()` with role_type (AI, human, tool) |
| **Business data ingestion** | Any data type via API or channels | `graph.add()` for JSON, text, structured data |

**Verdict:** mem-dog wins significantly. Zep ingests data only through SDK calls (`memory.add` for chat, `graph.add` for data). mem-dog supports 25+ channels with DigiMe as an AI agent for querying the RAG system and ingesting data through conversation.

### Memory Architecture

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Memory model** | 10 explicit types (timeline, session, conversation, user, organizational, factual, episodic, semantic, custom, tracing) | Implicit via knowledge graph — user threads, user graphs, shared graphs |
| **Chat history** | Stored as data items, queryable via RAG | First-class abstraction: Users → Threads → Messages with automatic summarization |
| **Memory levels** | 10 types grouped into 4 categories | 3 patterns: user threads (session), user graphs (personal), shared graphs (organizational) |
| **Versioning** | Every mutation creates a new version with diff tracking | Temporal edges (created/expired/valid/invalid timestamps) |
| **Access control** | Per-item ACLs (private, shared, public, restricted) + `shared_with` user list | User-scoped graphs + shared graphs |
| **Expiry/TTL** | Default TTL per type, override with `ttl_hours` or `no_expiry` | Temporal edge invalidation (facts expire but are preserved for history) |
| **Memory compression** | LLM summarization with archive, auto-trigger at threshold | Automatic summarization of chat histories |
| **Context assembly** | RAG chat builds context from relevant data + entities | `memory.get()` returns pre-assembled, prompt-ready context string |

**Verdict:** Different approaches. Zep's temporal graph provides sophisticated context assembly — `memory.get()` returns a ready-to-use context string. mem-dog offers more explicit control with 10 memory types, versioning, and granular ACLs. Zep is more opinionated (and easier for chat-focused apps); mem-dog is more flexible.

### Knowledge Graph

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Graph engine** | Dual-layer: Postgres tables + Graphiti/Neo4j temporal knowledge graph | Graphiti — temporal knowledge graph with episodic, entity, and community nodes |
| **Temporal awareness** | Graphiti temporal facts with valid_at/invalid_at + point-in-time queries | 4 timestamps per edge: t_created, t_expired, t_valid, t_invalid |
| **Entity extraction** | Automatic in webhook pipeline (typed_entities + relationships) | Automatic from chat and `graph.add()` data |
| **Entity types** | 8 fixed: person, organization, product, location, date, url, concept, event | Dynamically extracted by LLM |
| **Fact evolution** | New version replaces old | Old facts invalidated (not deleted), history preserved |
| **Community detection** | None | Label propagation algorithm for higher-level pattern discovery |
| **Graph search** | 5 modes: vector, FTS, hybrid (RRF), graph (Graphiti BFS+semantic), full (all signals merged) | 3 concurrent strategies: cosine similarity + BM25 + graph traversal |
| **Reranking** | 4 strategies: RRF, MMR, cross-encoder, node distance | 4 strategies: RRF, MMR, episode-mentions, node distance |
| **Dedup** | Canonical form unique index (user_id + type + lowered name) | LLM-based conflict detection + entity resolution |
| **Infrastructure** | Postgres (zero-infra) + optional Neo4j for Graphiti | Neo4j or embedded graph (Graphiti) |
| **Cost** | Free (Postgres) + optional Neo4j | Managed cloud pricing or self-hosted Neo4j |

**Verdict:** Now comparable. mem-dog integrates Graphiti (Zep's own open-source engine) alongside Postgres, gaining temporal knowledge graphs, BFS traversal, and multi-signal search with 4 reranking strategies. Postgres layer remains zero-infra for basic entity-aware RAG; Neo4j is optional for advanced temporal reasoning.

### AI Enrichment

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Automatic processing** | 40 typed sub-agents process every piece of data at ingest | LLM extracts facts and entities from messages/data |
| **Data type coverage** | 60+ types: PDFs, images, video, audio, code, medical, geospatial, IoT | Text conversations and structured/unstructured text data |
| **Classification** | 6-layer cascade (deterministic first, LLM fallback) | Automatic entity/relationship classification |
| **Viewpoints** | LLM-generated analysis stored as versioned viewpoints | None |
| **Auto-tagging** | Category, entity, keyword tags extracted automatically | Entity and relationship tagging via graph |
| **Model routing** | 5 tiers: small (4b) → medium (12b) → large (27b) → multimodal → omni | Single model configuration |

**Verdict:** mem-dog wins on breadth. Zep focuses on extracting facts/entities from text for the knowledge graph. mem-dog processes 60+ data types through 40 specialized agents with tiered model routing.

### Query & Search

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Semantic search** | pgvector cosine similarity | 1024-dim embeddings with cosine similarity |
| **Full-text search** | BM25 via tsvector on embeddings table | BM25 keyword matching |
| **Graph-augmented search** | 5 modes: vector, FTS, hybrid (RRF), graph (Graphiti BFS+semantic), full (all merged) | Breadth-first graph traversal from origin nodes |
| **RAG chat** | Conversational with inline [1] [2] citations + history, all 5 search modes | None — returns context for you to inject into your LLM |
| **Context assembly** | You build the prompt from search results | `memory.get()` returns assembled context string + raw facts + chat history |
| **Reranking** | 4 strategies: RRF, MMR, cross-encoder, node distance | 4 strategies (RRF, MMR, episode-mentions, node distance) |
| **Query modes** | 7: vector, FTS, hybrid, graph, full, timeline-scoped, conversational chat | `memory.get()` (context) + `graph.search()` (facts) |
| **Temporal queries** | Point-in-time fact queries via Graphiti temporal filters | Native temporal edge queries |
| **Web UI search** | Full-text search, tag faceting, data browser | None (API/SDK only) |

**Verdict:** Now comparable in search sophistication. mem-dog offers 5 search modes with 4 reranking strategies, temporal queries, and built-in RAG chat with citations. Zep's `memory.get()` automatic context assembly is still simpler for agent-facing use. mem-dog gives you both a conversational answer (human-facing) and raw results (agent-facing).

### Developer Experience

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Simple SDK** | `MemDog` with 7 methods (add, search, get, delete, entities, related, compress) | `memory.add()`, `memory.get()`, `graph.add()`, `graph.search()` |
| **Full SDK** | `MemDogClient` with 70+ methods (every API endpoint) | User/Thread/Memory/Graph APIs |
| **Language SDKs** | Python, TypeScript, Go, Ruby, Rust | Python, TypeScript, Go |
| **Agent adapters** | LangChain, CrewAI, OpenAI function calling | MCP server, direct SDK integration |
| **MCP server** | Yes | Yes |
| **API endpoints** | 60+ REST endpoints | ~10 REST endpoints |
| **Async support** | Python SDK is sync only | Python SDK supports sync + async |

**Verdict:** Comparable. mem-dog now has 5 language SDKs (Python, TypeScript, Go, Ruby, Rust) vs. Zep's 3 (Python, TypeScript, Go). Zep's API is simpler and more opinionated. mem-dog has far more endpoints for advanced control.

### User & Session Management

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **User model** | Users with API keys, scoped by user_id | First-class User abstraction with metadata |
| **Sessions** | Memory types (session, conversation) with TTL | Threads — first-class session objects tied to users |
| **Chat history** | Stored as data items | Automatic: timestamped, archived, summarized, embedded |
| **GDPR deletion** | Delete user + cascade data | Single API call deletes user + all threads + artifacts |
| **Regulatory compliance** | Version history + OTel traces | Zep Archive — records retention for compliance |

**Verdict:** Zep wins for chat-centric applications. Users → Threads → Messages is a clean, purpose-built hierarchy with automatic summarization and archival. mem-dog's model is more general but requires more manual orchestration for chat workflows.

### Deployment & Infrastructure

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Managed service** | None | Zep Cloud |
| **Self-hosted** | Docker Compose (1 command), GKE, Mac Mini | Graphiti (open-source engine) + BYO infrastructure |
| **Local dev** | `docker compose up` → 9 services running | pip install + configure |
| **Production** | GKE + Cloud Run with deploy scripts | Managed cloud or self-hosted |
| **Model flexibility** | 5 tiers, Model Garden (10+ providers), BYO API key | Configurable LLM |
| **Offline capable** | Fully functional with local Ollama | Requires LLM API access |

**Verdict:** Zep wins on ease of start (managed cloud). mem-dog wins on self-hosted production with deploy scripts, Mac Mini support, and offline capability.

### Security & Compliance

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Authentication** | Supabase Auth (email + Google OAuth) + per-user API keys | API key |
| **Encryption** | Fernet AES-256 for credentials at rest | Managed cloud security |
| **Per-item ACLs** | private, shared, public, restricted | User-scoped + shared graphs |
| **SOC 2 / HIPAA** | No | Via managed cloud (Enterprise) |
| **Audit trail** | OpenTelemetry traces + version history | Zep Archive (records retention) |

**Verdict:** Zep wins on enterprise compliance via managed platform. mem-dog has stronger per-item access control for self-hosted deployments.

### Web UI

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Data browser** | Full CRUD with search, filter, tag faceting | None (API/SDK only) |
| **RAG chat** | Conversational interface with inline citations | None |
| **Upload** | 6 input modes (text, file, URL, camera, voice, video) | None |
| **Testing** | Webhook simulator for 10+ channel types | None |
| **AI settings** | Model garden, smart routing, agent configs, prompts | None |
| **Dashboard** | Stats, token usage, OTel traces | Cloud dashboard (managed only) |

**Verdict:** mem-dog wins. Full web UI vs. API/SDK-only.

### Token Cost & Local Models

| Feature | mem-dog | Zep |
|---------|---------|-----|
| **Local model support** | First-class — Ollama in-cluster (GKE sidecar or standalone) | None — cloud LLM APIs |
| **Default processing model** | Gemma3:4b (local, free) for ~80% of data types | Cloud LLM (configurable) |
| **Classification cost** | 6-layer deterministic cascade — LLM is layer 5 fallback | LLM-based extraction on every ingestion |
| **Embedding model** | Self-hosted `nomic-embed-text` (free) or Gemini | 1024-dim embeddings (cloud) |
| **Offline capable** | Fully functional with local Ollama | Requires internet |
| **GPU requirement** | 8GB VRAM for Gemma3:4b (Mac Mini M2 works) | None (cloud-hosted) |

**Verdict:** mem-dog wins on cost at scale. Local-first models mean most processing is free. Zep's cloud-only approach is simpler but costs more at volume.

---

## Where mem-dog Leads

1. **Multi-channel ingestion** — 25+ channels vs. SDK-only
2. **AI enrichment pipeline** — 40 typed agents vs. text fact extraction
3. **Data type coverage** — 60+ types (media, spatial, IoT, medical) vs. text
4. **RAG chat with citations** — built-in conversational search with 5 search modes vs. context assembly for external LLM
5. **Web UI** — full management platform vs. API-only
6. **Memory types** — 10 types with TTL, ACLs vs. implicit graph-based memory
7. **Search modes** — 5 modes (vector, FTS, hybrid, graph, full) + 4 reranking strategies
8. **Temporal knowledge graph** — same Graphiti engine as Zep, integrated alongside pgvector
9. **Language SDKs** — 5 languages (Python, TypeScript, Go, Ruby, Rust) vs. 3 (Python, TypeScript, Go)
10. **Model Garden** — 10+ AI providers, per-user/per-type model selection vs. single model config
11. **Token cost savings** — local-first models, 60-80% cheaper at scale
12. **Offline capability** — fully functional without internet
13. **Self-hosted production** — deploy scripts, Mac Mini support, full infra ownership

## Where Zep Leads

1. **Context assembly** — `memory.get()` returns prompt-ready context (not raw results)
2. **Chat-first architecture** — Users → Threads → Messages with automatic summarization and archival
3. **Managed service** — zero-ops cloud platform
4. **GDPR / privacy** — single-call user deletion with cascade, Zep Archive for compliance
5. **Incremental graph updates** — no full recomputation when adding new data
6. **Benchmark performance** — 18.5% accuracy improvement over baselines on DMR benchmark, 90% latency reduction
7. **Community detection** — label propagation for higher-level pattern discovery (mem-dog uses Graphiti but doesn't expose community APIs yet)

## Where They're Comparable

- Knowledge graph entity extraction (different approaches, both automatic)
- Agent framework support (MCP server, LangChain/CrewAI)
- Per-user data isolation
- Python and TypeScript SDKs
- Memory summarization / compression

---

## Bottom Line

**Zep** is the right choice if you're building AI agents that need sophisticated conversational memory with temporal awareness — it understands that facts change over time, automatically assembles context, and its graph search combines semantic, keyword, and structural retrieval. The managed cloud eliminates ops. Best for: chat agents, customer support bots, personal assistants.

**mem-dog** is the right choice if you need a complete private AI system — multi-channel ingestion, AI enrichment of any data type, built-in RAG chat, full web UI, and cost-effective self-hosted deployment. Best for: organizational knowledge management, multi-modal data processing, privacy-sensitive deployments.

Key differentiator: mem-dog now integrates Graphiti (Zep's own open-source engine) for temporal knowledge graphs, closing the graph sophistication gap. mem-dog adds 5 search modes, 4 reranking strategies, and temporal fact queries on top of its existing breadth (25+ channels, 60+ data types, 40 agents, 5 SDKs, full web UI). Zep still leads on context assembly (`memory.get()` returns prompt-ready strings) and managed cloud deployment.

They solve related but distinct problems:
- Zep = **context engine for your agent** (managed cloud + context assembly)
- mem-dog = **private AI for your organization** (self-hosted system + same Graphiti engine)
