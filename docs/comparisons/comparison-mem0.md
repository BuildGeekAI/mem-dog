# mem-dog vs mem0: Detailed Comparison

**Last updated:** March 2026

mem0 is the most popular AI memory framework (49.8k GitHub stars, $24M Series A, Apache 2.0). This document compares mem-dog against mem0 feature-by-feature to identify where mem-dog leads, where mem0 leads, and where they're comparable.

---

## At a Glance

| | mem-dog | mem0 |
|-|---------|------|
| **What it is** | Private AI memory platform with multi-channel ingestion, AI pipeline, and query engine | Memory layer SDK for adding persistent memory to AI agents |
| **Focus** | End-to-end data lifecycle: ingest, enrich, store, query | Memory CRUD: add, search, get, update, delete |
| **Deployment** | Self-hosted only (Docker, GKE, Mac Mini) | Managed cloud + self-hosted open source |
| **License** | Proprietary | Apache 2.0 |
| **Pricing** | Free (self-hosted) | Free tier → $19/mo → $249/mo → Enterprise |

---

## Feature-by-Feature Comparison

### Data Ingestion

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Multi-channel ingestion** | 25+ channels (WhatsApp, Telegram, Slack, Discord, Signal, email, etc.) via DigiMe agent | None — API-only ingestion |
| **Web UI upload** | 6 modes: text, file, URL, camera, voice, video | None |
| **Webhook pipeline** | Real-time NATS streaming with typed message routing | None |
| **Integration platform** | 300+ providers with OAuth2, API-key auth, encrypted credentials | None |
| **Channel agent** | DigiMe — AI agent in messaging apps that queries the mem-dog RAG system, performs semantic search, and ingests data through conversation | Browser extension for ChatGPT, Perplexity, Claude |

**Verdict:** mem-dog wins significantly. mem0 is API-only — data enters via `memory.add()` calls. mem-dog supports 25+ channels with DigiMe as an AI agent for querying the RAG system and ingesting data through conversation, plus a web UI for manual upload.

### AI Enrichment

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Automatic processing** | 40 typed sub-agents process every piece of data at ingest | LLM extracts facts from `add()` calls |
| **Data type coverage** | 60+ types: PDFs, images, video, audio, code, medical, geospatial, IoT | Text conversations only |
| **Classification** | 6-layer cascade (deterministic first, LLM fallback) | None — all text |
| **Viewpoints** | LLM-generated analysis stored as versioned viewpoints | None |
| **Auto-tagging** | Category, entity, keyword tags extracted automatically | None |
| **Model routing** | 5 tiers: small (4b) → medium (12b) → large (27b) → multimodal → omni | Single model (GPT-4 Nano default) |
| **Customizable prompts** | Per-agent-type configurable prompts, output schemas, skills | Custom prompt for entity extraction |

**Verdict:** mem-dog wins. mem0 focuses on extracting facts from conversations. mem-dog processes any data type through specialized agents with tiered model routing.

### Memory & Storage

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Memory types** | 10 types (timeline, session, conversation, user, organizational, factual, episodic, semantic, custom, tracing) | 3 levels (user, session, agent) |
| **Versioning** | Every mutation creates a new version with diff tracking | None |
| **Access control** | Per-item ACLs (private, shared, public, restricted) + `shared_with` user list | user_id scoping |
| **Expiry/TTL** | Default TTL per type, override with `ttl_hours` or `no_expiry` | None |
| **Storage backends** | 3: local filesystem, GCS, Supabase (Postgres + pgvector) | Vector DB (Qdrant, Chroma, etc.) + graph DB |
| **Binary storage** | GCS for images, PDFs, audio, video | Text only |
| **Memory compression** | LLM summarization with archive, auto-trigger at threshold | Intelligent compression built into core pipeline |
| **Memory categories** | 4 Mem0-aligned categories: conversation, session, user, organizational | 3: user, session, agent |

**Verdict:** mem-dog has more memory structure (10 types, versioning, ACLs, TTL). mem0 has simpler, more opinionated memory that "just works" for conversation state.

### Knowledge Graph

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Graph storage** | Dual-layer: Postgres tables + Graphiti/Neo4j temporal graph | Neo4j, Memgraph, AWS Neptune, Kuzu |
| **Temporal awareness** | Graphiti temporal facts with valid_at/invalid_at + point-in-time queries | None |
| **Entity extraction** | Automatic in webhook pipeline + Graphiti's own LLM extraction | LLM extraction on `memory.add()` |
| **Entity types** | 8: person, organization, product, location, date, url, concept, event | Extracted dynamically by LLM |
| **Dedup** | Canonical form unique index + Graphiti LLM-based entity resolution | LLM-based conflict detection |
| **Entity-aware RAG** | Entities injected into system prompt + graph BFS traversal | Graph results in separate `relations` key |
| **Graph search** | 5 modes: vector, FTS, hybrid (RRF), graph (BFS+semantic), full | Vector search only |
| **Reranking** | 4 strategies: RRF, MMR, cross-encoder, node distance | None |
| **Infrastructure** | Postgres (zero infra) + optional Neo4j for temporal graph | Requires separate Neo4j/Memgraph instance |
| **Cost** | Free (Postgres) + optional Neo4j | Neo4j Aura: $65+/mo; self-hosted: ops overhead |

**Verdict:** mem-dog wins. Dual-layer graph (Postgres + Graphiti/Neo4j) provides both zero-infra entity-aware RAG and advanced temporal reasoning with 5 search modes and 4 reranking strategies. mem0 supports more graph DB backends but lacks temporal awareness, multi-signal search, and reranking.

### Query & Search

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Semantic search** | pgvector cosine similarity | Vector DB (Qdrant, Chroma, etc.) |
| **Full-text search** | BM25 via tsvector on embeddings table | None |
| **Graph search** | Graphiti BFS + semantic on Neo4j temporal knowledge graph | None |
| **Hybrid search** | Vector + BM25 + graph merged with RRF | None |
| **RAG chat** | Conversational with inline [1] [2] citations, all 5 search modes | Not built-in (memory feeds into external LLM) |
| **Reranking** | 4 strategies: RRF, MMR, cross-encoder, node distance | None |
| **Temporal queries** | Point-in-time fact retrieval via Graphiti | None |
| **Query modes** | 7: vector, FTS, hybrid, graph, full, timeline-scoped, conversational chat | `memory.search()` returns relevant memories |
| **Web UI search** | Knowledge Chat with search mode selector + reranking controls | Dashboard (managed platform) |

**Verdict:** mem-dog wins significantly. 5 search modes with 4 reranking strategies, temporal queries, and built-in RAG chat with citations. mem0's search returns memories that you feed into your own LLM.

### Developer Experience

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Simple SDK** | `MemDog` with 8 methods (add, search, get, delete, entities, related, compress) | `Memory` with 5 methods (add, search, get, update, delete) |
| **Full SDK** | `MemDogClient` with 70+ methods (every API endpoint) | Same 5 methods |
| **Language SDKs** | Python | Python + TypeScript/JavaScript |
| **Agent adapters** | LangChain (ChatMessageHistory + Retriever), CrewAI, OpenAI function calling | LangGraph, CrewAI, Vercel AI SDK |
| **MCP server** | Yes | Yes |
| **API endpoints** | 60+ REST endpoints | ~5 REST endpoints |
| **Documentation** | 12 docs covering architecture, API, pipeline, deployment, graph, etc. | Comprehensive docs site |

**Verdict:** Mixed. mem0 has TypeScript SDK and simpler API surface. mem-dog has far more API endpoints and the full REST client, but only Python. Agent adapter coverage is comparable.

### Deployment & Infrastructure

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Managed service** | None | mem0 Cloud (app.mem0.ai) |
| **Self-hosted** | Docker Compose (1 command), GKE, Mac Mini | pip install + configure backends |
| **Local dev** | `docker compose up` → 9 services running | `pip install mem0ai` + external vector DB |
| **Production** | GKE + Cloud Run with deploy scripts | Bring your own infra or use managed |
| **Model flexibility** | 5 tiers, Model Garden (10+ providers), BYO API key | OpenAI default, configurable LLM |
| **Storage flexibility** | 3 backends (local, GCS, Supabase) | Multiple vector DBs + graph DBs |

**Verdict:** mem0 wins on ease of getting started (pip install + managed cloud). mem-dog wins on self-hosted production deployment with deploy scripts, Mac Mini support, and full infrastructure control.

### Security & Compliance

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Authentication** | Supabase Auth (email + Google OAuth) + per-user API keys | API key |
| **Encryption** | Fernet AES-256 for credentials at rest | Not specified (open source) |
| **Per-user scoping** | Every query scoped by user_id | user_id scoping |
| **Per-item ACLs** | private, shared, public, restricted | None |
| **SOC 2** | No | Yes (managed platform) |
| **HIPAA** | No | Yes (managed platform, BYOK) |
| **Audit trail** | OpenTelemetry traces + version history | Audit logs (Enterprise) |

**Verdict:** mem0 wins on enterprise compliance (SOC 2, HIPAA) via managed platform. mem-dog has stronger per-item access control and versioning for self-hosted deployments.

### Observability

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Distributed tracing** | OpenTelemetry across all components | None (open source) |
| **Span viewer** | Waterfall UI in Insights tab | Analytics dashboard (managed) |
| **Token tracking** | Per-user, per-model, per-agent breakdown | Usage analytics (managed) |
| **Stats dashboard** | Data counts, embeddings, memories, agent performance | Memory analytics (Pro+) |

**Verdict:** mem-dog wins for self-hosted observability. mem0 managed platform has its own analytics.

### Web UI

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Data browser** | Full CRUD with search, filter, tag faceting | None (open source) |
| **RAG chat** | Conversational interface with inline citations | None |
| **Upload** | 6 input modes (text, file, URL, camera, voice, video) | None |
| **Testing** | Webhook simulator for 10+ channel types | None |
| **AI settings** | Model garden, smart routing, agent configs, prompts | None |
| **Dashboard** | Stats, token usage, OTel traces | Dashboard (managed platform) |

**Verdict:** mem-dog wins. Full web UI vs. API-only for open source mem0.

### Model Garden & AI Providers

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Provider management** | Model Garden UI — connect 10+ providers (OpenAI, Anthropic, Gemini, Groq, Mistral, Cohere, DeepSeek, xAI, Ollama, Ollama Cloud) with encrypted API keys | Single LLM config (default: GPT-4 Nano) |
| **Model discovery** | Auto-discovers available models per provider via API introspection | Manual model name configuration |
| **Per-user model selection** | Each user picks their own provider/model from connected options | Global setting |
| **Per-data-type routing** | Override model per agent type (e.g. use GPT-4o for images, Gemma3:4b for text) | Single model for all operations |
| **Smart routing** | 5-tier automatic routing: small (4b) → medium (12b) → large (27b) → multimodal → omni | N/A |
| **Tiered complexity** | Simple data → small local model; complex/multimodal → large cloud model | Same model regardless of complexity |
| **Key encryption** | Fernet AES-256 encryption for all API keys at rest | Not specified |
| **Fallback chain** | Local Ollama → Ollama Cloud → Gemini (automatic failover) | Single provider |
| **BYO model** | Any OpenAI-compatible endpoint via custom base URL | Limited to supported providers |
| **UI management** | Full settings page: add/remove providers, test connections, set defaults | None (config file or API) |

**Verdict:** mem-dog wins significantly. Model Garden gives users and admins full control over which AI providers and models are used, per-user and per-data-type. mem0 locks you into a single model configuration.

### Token Cost & Local Models

| Feature | mem-dog | mem0 |
|---------|---------|------|
| **Local model support** | First-class — Ollama in-cluster (GKE sidecar or standalone) | None — cloud APIs only |
| **Default processing model** | Gemma3:4b (local, free) for ~80% of data types | GPT-4 Nano (cloud, usage-based) |
| **Classification cost** | 6-layer deterministic cascade — LLM is layer 5 fallback (rarely needed) | LLM-based extraction on every `add()` call |
| **Embedding model** | Self-hosted `nomic-embed-text` (free) or Gemini (low cost) | OpenAI `text-embedding-3-small` ($0.02/1M tokens) |
| **Cost per 1K ingestions** | ~$0 (local models) to ~$0.10 (cloud fallback for complex types) | ~$0.50–$2.00 (cloud API calls for extraction + embedding) |
| **Monthly cost at scale** (10K items/mo) | ~$0–$1 (local) + compute ($50–100 for GKE node) | ~$5–20 (API usage) + $249/mo (Pro plan for unlimited) |
| **Multimodal cost control** | Only routes images/video to expensive models; text stays on 4b | Same model for all content types |
| **Token tracking** | Per-user, per-model, per-agent breakdown in UI | Usage analytics (managed Pro+) |
| **Cold start** | Models pre-loaded in Ollama — no API latency | Cloud API latency per request |
| **Offline capable** | Fully functional with local Ollama (no internet needed) | Requires internet for all operations |
| **GPU requirement** | 8GB VRAM for Gemma3:4b (Mac Mini M2 works) | None (cloud-hosted) |

**Cost breakdown example — 10,000 items/month:**

| Cost component | mem-dog (local-first) | mem0 (cloud) |
|----------------|----------------------|--------------|
| Classification | $0 (deterministic rules) | Included in add() |
| LLM enrichment | $0 (Gemma3:4b local) | ~$5–10 (GPT-4 Nano) |
| Embeddings | $0 (nomic-embed local) | ~$2 (text-embedding-3-small) |
| Graph extraction | $0 (local LLM) | N/A (Pro only) |
| Platform fee | $0 | $249/mo (Pro) or $19/mo (Starter, 50K cap) |
| **Compute infra** | **$50–100/mo** (GKE node or Mac Mini amortized) | **$0** (managed) |
| **Total** | **~$50–100/mo** | **~$260–280/mo** |

At 10K items/month, mem-dog costs 60–80% less. The gap widens at scale because mem-dog's local model costs are fixed (compute) while mem0's API costs grow linearly with volume.

**Verdict:** mem-dog wins on cost at scale. The 5-tier routing with local-first models means most processing is free. The 6-layer deterministic classification avoids LLM calls entirely for type detection. mem0's cloud-only approach is simpler to set up but costs significantly more at volume.

---

## Pricing Comparison

| | mem-dog | mem0 Free | mem0 Starter | mem0 Pro | mem0 Enterprise |
|-|---------|-----------|-------------|----------|----------------|
| **Cost** | Free (self-hosted) | $0/mo | $19/mo | $249/mo | Custom |
| **Memories** | Unlimited | 10K | 50K | Unlimited | Unlimited |
| **Graph memory** | Included | No | No | Yes | Yes |
| **Retrieval calls** | Unlimited | 1K/mo | 5K/mo | Unlimited | Unlimited |
| **Compression** | Included | Yes | Yes | Yes | Yes |
| **SOC 2 / HIPAA** | No | No | No | No | Yes |

mem-dog is free but requires self-hosting (compute costs for GKE/Cloud Run or a Mac Mini). mem0's managed platform eliminates ops but costs $249/mo for full features.

---

## Where mem-dog Leads

1. **Multi-channel ingestion** — 25+ channels vs. API-only
2. **AI enrichment pipeline** — 40 typed agents vs. fact extraction
3. **Data type coverage** — 60+ types (media, spatial, IoT, medical) vs. text
4. **RAG chat with citations** — built-in vs. bring your own
5. **Web UI** — full management platform vs. API-only (open source)
6. **Versioning** — every mutation tracked vs. none
7. **Memory types** — 10 types with TTL, ACLs vs. 3 levels
8. **Model Garden** — 10+ AI providers, per-user/per-type model selection, encrypted keys vs. single model config
9. **Token cost savings** — local-first models (Gemma3:4b free) + 5-tier smart routing + deterministic classification = 60-80% cheaper at scale
10. **Self-hosted control** — deploy scripts, Mac Mini, full infra ownership
11. **Knowledge graph** — dual-layer (Postgres + Graphiti/Neo4j) with temporal reasoning, 5 search modes, 4 rerankers
12. **Temporal queries** — point-in-time fact retrieval ("Who was CEO in 2024?")
13. **Offline capable** — fully functional with local Ollama, no internet required

## Where mem0 Leads

1. **Ease of getting started** — `pip install mem0ai` + 5 lines of code
2. **Managed service** — zero ops cloud platform
3. **Enterprise compliance** — SOC 2, HIPAA, BYOK
4. **TypeScript SDK** — Python + JS vs. Python only
5. **Graph DB options** — Neo4j, Memgraph, Neptune, Kuzu (mem-dog uses Postgres + Neo4j/Graphiti)
6. **Community** — 49.8k GitHub stars, large ecosystem
7. **Research validation** — published paper, LOCOMO benchmark (26% uplift vs. OpenAI)
8. **AWS partnership** — exclusive memory provider for Strands Agent SDK
9. **Memory intelligence** — sophisticated conflict detection, fact dedup, background summarization
10. **Simplicity** — 5 methods is all you need for most use cases

## Where They're Comparable

- Knowledge graph (different approaches, similar outcomes)
- Agent framework adapters (LangChain, CrewAI)
- Memory compression / summarization
- MCP server support
- Per-user data isolation
- Python SDK

---

## Bottom Line

**mem0** is the right choice if you want a simple, drop-in memory layer for an AI agent — add 5 lines of code and memories persist across sessions. The managed platform handles infrastructure, and enterprise compliance is built in.

**mem-dog** is the right choice if you want a complete private AI memory platform — multi-channel ingestion, automatic AI enrichment of any data type, temporal knowledge graph (Graphiti + Neo4j), 5-mode search with reranking, built-in RAG chat with citations, and full infrastructure ownership. It does more, but requires self-hosting.

They solve different problems at different scales:
- mem0 = **memory for your agent** (SDK)
- mem-dog = **private AI for your organization** (self-hosted system)
