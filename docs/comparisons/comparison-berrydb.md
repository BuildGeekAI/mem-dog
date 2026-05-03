# memdog vs BerryDB: Detailed Comparison

**Last updated:** March 2026

BerryDB (berrydb.io) is a multi-modal knowledge graph database with ML workflow management. It positions itself as "the missing layer between raw data lakes and AI agents," handling docs, PDFs, images, audio, and video in a semantically connected layer. This document compares memdog against BerryDB feature-by-feature.

---

## At a Glance

| | memdog | BerryDB |
|-|---------|---------|
| **What it is** | Private AI system with multi-channel ingestion, 40-agent enrichment pipeline, and RAG query engine | Multi-modal knowledge graph database with ML workflow management |
| **Focus** | End-to-end data lifecycle: ingest from channels → AI enrichment → store → search/RAG | Store multi-modal data, build knowledge graphs, annotate, train models |
| **Deployment** | Self-hosted only (Docker Compose, GKE, Mac Mini) | SaaS only (30-day free trial) |
| **License** | Proprietary | Proprietary |
| **Pricing** | Free (self-hosted hardware costs only) | SaaS pricing (not published) |
| **Core engine** | 40-agent webhook pipeline + pgvector + Postgres + Neo4j/Graphiti | Purpose-built knowledge graph DB with multi-modal processing |

---

## Feature-by-Feature Comparison

### Data Ingestion

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **Real-time channels** | 25+ messaging channels (WhatsApp, Signal, Telegram, Slack, Discord, iMessage, etc.) via DigiMe agent + 300+ integrations (Gmail, Zoom, etc.) via Nango | None — SDK/API upload only |
| **Web UI upload** | 6 modes: text, file, URL, camera, voice, video | Notebook UI for processing unstructured data |
| **Webhook pipeline** | Real-time NATS streaming → 40 typed sub-agents auto-classify, extract, embed | PDF ingestion, NER, sentiment, classification |
| **Auto-enrichment** | 6-layer routing: explicit field → LLM classifier → MIME registry → URL extension → fallback | Pipeline processing (less documented) |
| **Push vs Pull** | Push — data flows in automatically from connected channels | Pull — you call the SDK to ingest |
| **Multi-modal** | Text, files, URLs, images (via Qwen3-VL multimodal model) | First-class: PDF, text, images, audio, video, JSON |

**Verdict:** memdog wins on real-time ingestion — data flows in automatically from 300+ sources. BerryDB wins on native multi-modal support (audio/video are first-class). If your data comes from messaging channels and integrations, memdog is far ahead. If you're batch-processing media files, BerryDB has better native support.

### Conversational AI Agent

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **Built-in agent** | DigiMe (OpenClaw Node) — conversational AI across 25+ channels | None |
| **Channel support** | WhatsApp, Signal, Telegram, Discord, Slack, Matrix, IRC, iMessage, LINE, Google Chat, Teams, Mattermost, Nostr, Twitch, and more | N/A |
| **Multi-user isolation** | Channel identity resolution: `(channel_type, peer_id) → user_id`, each user's data fully scoped | N/A |
| **Memory behavior** | Every message auto-recorded → pipeline → classified → searchable | N/A |
| **Recall** | Natural language recall ("What time is my flight?") → semantic search scoped to user | N/A |
| **Skills** | 4 skills: bridge (record), ingest (store), query (lookup), semantic-search (recall) | N/A |

**Verdict:** memdog wins decisively. DigiMe is a production AI agent that users interact with via their existing messaging apps. BerryDB has no agent layer — it's a database you call from your own code. Building an equivalent agent on top of BerryDB would require significant custom engineering.

### Search & Knowledge Graph

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **Vector search** | pgvector cosine similarity | Similarity search |
| **Full-text search** | BM25 keyword search | FTS support |
| **Hybrid search** | Vector + BM25 via Reciprocal Rank Fusion | Not documented |
| **Graph search** | Graphiti BFS traversal on Neo4j | Knowledge graph queries (purpose-built) |
| **Combined search** | All 4 signals merged + reranking | Not documented |
| **Rerankers** | 4: none, RRF, MMR (diversity), cross-encoder (LLM-scored) | Not documented |
| **Temporal facts** | `valid_at`/`invalid_at` timestamps — point-in-time retrieval | Not documented |
| **RAG chat** | `/api/v1/ai/query/chat` with `[1][2]` citation markers | RAG chat operations |
| **Knowledge graph type** | Dual-layer: Postgres (always) + Graphiti/Neo4j (optional, temporal) | Purpose-built, semantically connected |
| **Graph auto-creation** | Entities dual-written to Postgres + Neo4j from pipeline | Automatic from multi-modal data |

**Verdict:** Both have strong search. memdog offers more search modes (5) and rerankers (4) with temporal fact support. BerryDB's knowledge graph is purpose-built and likely more performant for graph-heavy workloads. memdog's advantage is combining all search signals (vector + BM25 + graph) into a single ranked result.

### AI Cost Optimization

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **Local LLMs** | Ollama (Gemma3 4b/12b/27b, embeddinggemma, Qwen3-VL) — $0/month | None — SaaS, provider-based |
| **Tiered model routing** | Small tasks → 4b, medium → 12b, large → 27b, multimodal → Qwen3-VL | Single provider per task |
| **Fallback chains** | Ollama → Ollama Cloud → Gemini (automatic failover) | Not documented |
| **Per-user model routing** | Different users/data types can use different providers | Not documented |
| **Model providers** | 10+: Ollama, Gemini, OpenAI, Anthropic, Groq, Together, Mistral, etc. | Hugging Face, Vertex AI, custom |
| **Local embeddings** | embeddinggemma ($0) or Gemini/OpenAI (optional) | Provider-based |
| **Pod management** | UI to create/scale/delete Ollama pods on K8s | N/A (SaaS) |

**Monthly cost comparison (moderate workload: ~10K items/month):**

| Cost item | memdog (self-hosted) | memdog (cloud LLMs) | BerryDB |
|-----------|----------------------|---------------------|---------|
| Embedding generation | $0 (local embeddinggemma) | $5-15 (Gemini API) | Unknown (SaaS) |
| Classification/enrichment | $0 (local gemma3:4b) | $10-30 (Gemini API) | Included in SaaS |
| Complex analysis | $0 (local gemma3:12b) | $20-50 (Gemini/GPT-4) | Included in SaaS |
| Vector DB | $0 (local pgvector) | $0 (local pgvector) | Included in SaaS |
| Knowledge graph | $0 (local Neo4j) | $0 (local Neo4j) | Included in SaaS |
| Infrastructure | $0 (Mac Mini, one-time) | $150-300/mo (GKE) | SaaS subscription |
| **Total recurring** | **$0/month** | **$185-395/month** | **Unknown** |

**Verdict:** memdog's tiered local model routing means ~80% of AI workload (tagging, simple extraction, embeddings) runs on the free 4b model. Only complex analysis escalates to larger models or cloud APIs. BerryDB's costs are opaque (SaaS pricing not published), but any SaaS with LLM processing has ongoing per-item costs.

### Data Privacy & Sovereignty

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **Data location** | Your hardware — Mac Mini, your GKE cluster, your Postgres | BerryDB's servers |
| **Who can access** | Only you | BerryDB team + you (shared responsibility) |
| **Data leaves your network** | No (fully local with Ollama) | Yes — every API call |
| **AI processing privacy** | Local Ollama — prompts never leave your machine | Their infra or third-party LLM providers |
| **Encryption at rest** | You control it (Postgres encryption, disk-level) | Managed by BerryDB |
| **Credential storage** | AES-256-GCM (Nango), Fernet for AI API keys | Managed by BerryDB |
| **Access control** | 4 levels: private, shared, public, restricted + `shared_with` user lists | Not documented |
| **Audit trail** | Full timeline of every data action | Not documented |
| **Air-gapped operation** | Yes — full stack runs without internet | Impossible (SaaS) |
| **Open source auditable** | Yes — inspect every line that touches your data | No — proprietary |
| **Data jurisdiction** | Data stays wherever your hardware is | Wherever their servers are |
| **GDPR right to erasure** | Delete from your Postgres — provably gone | Request deletion, trust compliance |

**Verdict:** memdog wins for any privacy-sensitive use case. The entire data pipeline — ingestion, AI processing, storage, search — runs on your hardware with zero third-party exposure. BerryDB is standard SaaS shared responsibility. For regulated industries (healthcare/HIPAA, legal/attorney-client privilege, finance, EU/GDPR), memdog's self-hosted model eliminates trust boundaries entirely.

**Privacy by architecture:**

```
memdog (local mode):
  User → DigiMe → Webhook Pipeline → Ollama (LOCAL) → Postgres (LOCAL)
  Trust boundaries: 0
  Third parties who see your data: 0

BerryDB:
  Your App → BerryDB SaaS → Their LLM Provider → Their Storage
  Trust boundaries: 2-3
  Third parties who see your data: 2-3
```

### Memory & Context System

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **Memory types** | 10 explicit: timeline, session, conversation, user, organizational, factual, episodic, semantic, custom, tracing | Not documented as a first-class concept |
| **Memory categories** | 4 Mem0-compatible: conversation, session, user, organizational | N/A |
| **TTL/expiry** | Per-type defaults (conversation=1h, session=24h, timeline=7d), overridable | Not documented |
| **Access levels** | private (default), shared, public, restricted + `shared_with` | Not documented |
| **Versioning** | Every mutation creates a new version with diff tracking | Not documented |
| **AI agent memory** | DigiMe auto-creates session memories, stores facts, recalls via semantic search | "Memory layer for AI agents" (mentioned, not detailed) |

**Verdict:** memdog has a mature, explicit memory system with 10 types, TTL, access controls, and versioning. BerryDB mentions "memory layer for AI agents" but provides no detail on the implementation.

### Model Lifecycle & ML Workflows

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **Model management** | Model Garden (provider config, routing, fallback chains) + K8s Pod management UI | Model Repo, Model Config, versioning |
| **Model training** | Not a focus — uses pre-trained models | Supports training workflows |
| **Annotation/labeling** | Not built-in | First-class: annotation projects, LLM-assisted labeling |
| **Model evaluation** | Not built-in | Evaluator module for model comparison |
| **Model providers** | 10+ (Ollama, Gemini, OpenAI, Anthropic, etc.) | Hugging Face, Vertex AI, custom |

**Verdict:** BerryDB wins for ML workflows. If you need to annotate data, train models, and evaluate them, BerryDB has purpose-built tooling. memdog focuses on using pre-trained models for enrichment and search, not training new ones.

### Deployment & Operations

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **Deployment options** | Docker Compose (Mac Mini), GKE, any Kubernetes | SaaS only |
| **Time to deploy** | ~30 min (Docker Compose) or ~2 hours (GKE) | Minutes (sign up + SDK) |
| **Preflight check** | `./scripts/preflight-check.sh` — verify resources before deploy | N/A |
| **Infrastructure management** | You manage it (K8s, Postgres, Neo4j, Ollama) | Fully managed |
| **Scaling** | Manual (K8s HPA, KEDA) or via Pod management UI | Horizontal auto-scaling (claims 5x faster than MongoDB) |
| **SDKs** | Python, TypeScript, Go, Rust, Ruby | Python, Java |
| **MCP integration** | MCP server with 8 tools for Claude Desktop/Cursor | Not documented |

**Verdict:** BerryDB wins on simplicity — sign up and start. memdog requires infrastructure knowledge but gives you complete control. The new Pod management UI (Settings > AI Config > Pods) reduces operational burden for model infrastructure.

### Integration Ecosystem

| Feature | memdog | BerryDB |
|---------|---------|---------|
| **OAuth integrations** | 300+ via Nango (Gmail, Slack, GitHub, Salesforce, etc.) | Not documented |
| **Messaging channels** | 25+ via OpenClaw (WhatsApp, Signal, Telegram, etc.) | None |
| **Webhook support** | Per-user webhook endpoints (`whk_<ulid>`) + gateway normalization | Not documented |
| **Push notifications** | Gmail push, Google Drive push, Zoom push | Not documented |
| **MCP (Model Context Protocol)** | SSE server with 8 tools for AI IDE integration | Not documented |

**Verdict:** memdog wins on integrations. 300+ OAuth providers + 25+ messaging channels + MCP for AI IDEs. BerryDB is SDK-first with no documented integration ecosystem.

---

## Use Case Matrix

| Use case | Best choice | Why |
|----------|------------|-----|
| Personal AI memory assistant | **memdog** | DigiMe on WhatsApp/Signal, local models, $0/month |
| Multi-modal media processing | **BerryDB** | Native image/audio/video understanding |
| Healthcare/legal (regulated data) | **memdog** | Air-gapped, zero third-party exposure, provable deletion |
| ML annotation & training | **BerryDB** | Purpose-built annotation, evaluation, model lifecycle |
| Real-time channel ingestion | **memdog** | 300+ integrations, 25+ messaging channels, auto-enrichment |
| Quick prototype / MVP | **BerryDB** | Sign up, SDK, start — no infra |
| Enterprise knowledge base | **memdog** | Multi-user isolation, 5 search modes, temporal knowledge graph, full audit trail |
| Cost-sensitive AI workloads | **memdog** | Tiered local Ollama ($0) vs SaaS recurring costs |
| Horizontal scaling at volume | **BerryDB** | Purpose-built for scale, managed infra |
| AI IDE integration (Claude/Cursor) | **memdog** | MCP server with 8 tools |

---

## Architecture Comparison

### memdog

```
Channels (25+ messaging + 300+ OAuth)
    ↓
Webhook Gateway (normalize, identity resolution)
    ↓
NATS JetStream (async queue)
    ↓
40 AI Sub-Agents (classify, extract, embed) ← Ollama (local, $0)
    ↓
API (FastAPI)
    ├── Postgres + pgvector (structured data, embeddings, memories)
    ├── Neo4j / Graphiti (temporal knowledge graph)
    └── GCS (raw binary storage)
    ↓
5 Search Modes + 4 Rerankers → RAG Chat with Citations
    ↓
DigiMe Agent (responds on user's messaging channel)
MCP Server (responds in Claude Desktop / Cursor)
Web UI (dashboard, settings, playground)
```

### BerryDB

```
Python/Java SDK
    ↓
BerryDB SaaS API
    ├── Multi-modal Processing (PDF, image, audio, video)
    ├── Knowledge Graph (semantically connected layer)
    ├── Annotation System (LLM-assisted labeling)
    └── Model Lifecycle (train, evaluate, version)
    ↓
Search (similarity, FTS) → RAG Chat
```

---

## Summary

memdog and BerryDB solve different problems with different philosophies:

- **memdog** is a **private AI platform** — it ingests data from real-time channels, enriches it with a 40-agent pipeline using free local models, and serves it via 5 search modes and a conversational AI agent across 25+ messaging channels. You own every byte.

- **BerryDB** is a **managed knowledge database** — it processes multi-modal data, builds knowledge graphs, and supports ML annotation/training workflows. It's simpler to start but requires sending your data to their cloud.

Choose memdog when privacy, cost control, real-time channel ingestion, or a conversational agent matters. Choose BerryDB when you need quick setup, native multi-modal processing, or ML training workflows.
