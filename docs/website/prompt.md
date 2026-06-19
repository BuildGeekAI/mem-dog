# Prompt: Build a Marketing Website for mem-dog

## Goal

Build a modern, high-converting marketing/landing website for **mem-dog** -- an open-source, self-hosted private AI memory platform. The site should position mem-dog as the best way for individuals and organizations to own their AI memory: ingest data from 300+ apps, enrich it with a 42-agent AI pipeline, store it with versioning and access control, and query it with 5 search modes powered by a temporal knowledge graph.

The site is purely promotional/informational -- it does NOT need authentication, a dashboard, or any backend. It should be a static site (Next.js static export, Astro, or similar) deployable to Vercel, Netlify, or Cloud Run.

---

## Brand & Positioning

- **Product name:** mem-dog
- **Tagline:** "The Private AI Memory Platform"
- **One-liner:** "Ingest data from 300+ apps, enrich it with a 42-agent AI pipeline, and query it with 5 search modes powered by a temporal knowledge graph -- all self-hosted and free."
- **License:** Apache 2.0
- **Target audience:** Developers, AI engineers, startups, and privacy-conscious individuals who want to own their memory layer instead of depending on cloud-only vendors like mem0, Zep, or Dify.
- **Tone:** Technical but approachable. Confident, not salesy. Let the features speak. Think Linear, Vercel, or Supabase marketing pages.
- **Color palette:** Dark mode primary. Use a deep navy/black background with electric blue (#3B82F6) and cyan (#06B6D4) accents. White text. Subtle gradients. The design should feel premium, technical, and modern.

---

## Pages & Sections

### 1. Landing Page (/)

This is the most important page. It should tell the full story in a single scroll.

#### Hero Section
- Large headline: **"The Private AI Memory Platform"**
- Subheadline: "Ingest from 300+ apps. Enrich with 42 AI agents. Query with 5 search modes. Self-hosted and free."
- Two CTA buttons: "Get Started" (links to quickstart/GitHub) and "View on GitHub" (links to repo)
- Below the CTAs, show a terminal-style code block:
  ```bash
  docker compose up
  # UI: localhost:3000 | API: localhost:8080 | Neo4j: localhost:7474
  ```
- Optionally, a screenshot or animated demo of the web UI (data browser, knowledge chat, or the architecture diagram)

#### "Why mem-dog?" Section
- 3-4 short paragraphs or cards explaining the problem and solution:
  - **The problem:** Your data lives in dozens of apps. AI memory tools only solve one slice -- mem0 is API-only, Zep is a context engine, Dify is a workflow builder. None of them handle the full lifecycle.
  - **The solution:** mem-dog is a complete platform: ingest from 300+ apps via Nango, enrich with 42 specialized AI agents, store with versioning and access control, and query across 5 search modes with a temporal knowledge graph.
  - **Private by design:** Self-hosted, local-first models (runs offline with Ollama), your data never leaves your infrastructure. Apache 2.0 licensed.

#### Feature Grid Section
Display these features in a visually rich grid (icons + short description for each):

1. **300+ App Integrations** -- Connect Slack, Gmail, GitHub, WhatsApp, Telegram, Discord, HubSpot, Salesforce, and 300+ more via Nango. OAuth2 with automatic token refresh and AES-256-GCM credential encryption.

2. **42-Agent AI Pipeline** -- Every piece of data is automatically classified, analyzed, summarized, and embedded by specialized agents. 60+ data types supported: PDFs, images, video, audio, code, medical records, geospatial data, IoT telemetry, and more.

3. **5 Search Modes** -- Vector (pgvector cosine similarity), full-text (BM25), hybrid (vector + BM25 via RRF), graph (Graphiti BFS on Neo4j), and full (all signals merged). Plus 4 reranking strategies: RRF, MMR, cross-encoder, and none.

4. **Temporal Knowledge Graph** -- Dual-layer: Postgres (always active, zero infra) + Graphiti/Neo4j (optional, temporal). Entities are dual-written. Facts have valid_at/invalid_at timestamps for point-in-time retrieval. "Who was CEO of Acme in 2024?" just works.

5. **RAG Chat with Citations** -- Conversational answers grounded in your data. Every claim is backed by numbered [1][2] citations linking back to source documents. Works with all 5 search modes and 4 rerankers.

6. **10 Memory Types** -- timeline, session, conversation, user, organizational, factual, episodic, semantic, custom, tracing. Grouped into 4 Mem0-compatible categories. Default TTLs per type, ACLs (private/shared/public/restricted), and per-item shared_with user lists.

7. **Smart Model Routing** -- 5 model tiers: small (4b) to omni. Per-agent-type assignment with fallback chains (Ollama local -> Ollama Cloud -> Gemini). Model Garden supports 10+ AI providers with per-user routing and encrypted API keys.

8. **Per-User Webhooks** -- Each user gets unique webhook endpoints (whk_<ulid>) with HMAC-SHA256 verification, event logging, and stats. 25+ channel adapters normalize payloads into a universal format.

9. **Multi-Language SDKs** -- Python, TypeScript, Go, Rust, Ruby. ~120 methods each, plus a 7-method simple facade. Agent adapters for LangChain, CrewAI, and OpenAI function calling. MCP server for Claude Desktop and Cursor.

10. **Self-Hosted & Free** -- Run on Docker Compose (local dev), GKE, or any Kubernetes cluster. No vendor lock-in, no usage fees. Apache 2.0 license.

#### Architecture Diagram Section
- Show the architecture as a visual diagram (can be an SVG or rendered Mermaid diagram). The data flow is:
  ```
  Data Sources (300+ Apps, Web UI, MCP Clients)
       |
  Webhook Gateway (normalize -> UniversalEnvelope)
       |
       +---> API (FastAPI, 70+ endpoints)
       +---> Webhook Pipeline (NATS, 42 agents: classify -> analyze -> embed)
                |
                +---> results back to API
       |
  Storage: Supabase Postgres (pgvector, BM25) + Neo4j (Graphiti KG) + GCS (raw binary) + Nango (OAuth tokens)
       |
  Search & Query: 5 modes -> 4 rerankers -> RAG Chat with citations
  ```
- Below the diagram, show a tech stack table:

  | Component | Stack | Deployment |
  |-----------|-------|------------|
  | API | Python 3.12, FastAPI | GKE |
  | UI | Next.js 14, TypeScript | Cloud Run |
  | MCP Server | Python 3.12, FastMCP, SSE | GKE |
  | Webhook Pipeline | Python 3.12, NATS, 42 agents | GKE |
  | Webhook Gateway | Python 3.12, FastAPI, LiteLLM | GKE |
  | Neo4j | Neo4j 5.26 Community + Graphiti | GKE |
  | Nango | OAuth, token refresh, encryption | GKE |
  | SDKs | Python, TypeScript, Go, Rust, Ruby | npm/pip/cargo |

#### Search Deep-Dive Section
- This section should be visually interesting (tabbed interface or interactive cards)
- Show each of the 5 search modes with a one-liner, a "best for" description, and an example curl command:

  | Mode | Engine | Best For |
  |------|--------|----------|
  | vector | pgvector (cosine similarity) | Semantic meaning, concept matching |
  | fts | BM25 keyword search | Exact terms, names, codes |
  | hybrid | Vector + BM25 via RRF | General-purpose (recommended default) |
  | graph | Graphiti BFS on Neo4j | Relationship traversal, temporal facts |
  | full | All signals merged | Maximum recall, complex questions |

- Show the 4 rerankers:

  | Reranker | Description |
  |----------|-------------|
  | none | Return results as-is |
  | rrf | Reciprocal Rank Fusion -- merge multiple rankings |
  | mmr | Maximal Marginal Relevance -- boost diversity |
  | cross-encoder | LLM-scored relevance -- highest quality |

- Include an example code snippet (curl or Python SDK) for hybrid search with MMR reranking and for RAG chat with citations.

#### Comparison Table Section
- Headline: "How mem-dog compares"
- A competitive comparison table. Make this visually clean with checkmarks and X marks:

  | Capability | mem-dog | mem0 | Zep | Dify.ai | LangMem |
  |-----------|---------|------|-----|---------|---------|
  | Multi-channel ingestion (300+ apps) | Yes | No | No | No | No |
  | Per-user webhook endpoints | Yes | No | No | No | No |
  | AI enrichment pipeline (42 agents) | Yes | No | No | Partial | No |
  | Temporal knowledge graph | Yes (Graphiti + Neo4j) | No | Yes (Graphiti) | No | No |
  | Multi-signal search (5 modes) | Yes | Vector only | Triple search | No | Vector only |
  | Reranking (RRF, MMR, cross-encoder) | Yes | No | Yes | No | No |
  | RAG chat with citations | Yes | No | No | Yes | No |
  | Web UI with playground | Yes | Dashboard (paid) | No | Yes | No |
  | 10 memory types with TTL/ACLs | Yes | 3 levels | Implicit | No | Partial |
  | Local-first models (offline capable) | Yes | No | No | Partial | No |
  | Self-hosted, free | Yes | Open source (limited) | Open source (Graphiti) | Open source | Open source |

- Below the table: "mem-dog = mem0 (memory) + Zep (knowledge graph) + Nango (integrations) + Dify (AI workflows) in one platform."

#### Quick Start Section
- Simple 3-step process with code blocks:
  1. **Clone & start:**
     ```bash
     git clone https://github.com/AkisAya/mem-dog.git
     cd mem-dog
     docker compose up
     ```
  2. **Open the UI:** `http://localhost:3000` -- browse data, chat, configure integrations
  3. **Use the SDK:**
     ```python
     from mem_dog_client import MemDog
     m = MemDog("http://localhost:8080")
     m.add("Meeting notes from Q3 planning session...", tags=["meetings", "Q3"])
     results = m.search("What was decided about the roadmap?")
     ```

#### Developer Experience Section
- Show SDK examples in multiple languages (tabbed code blocks):

  **Python:**
  ```python
  from mem_dog_client import MemDog
  m = MemDog("http://localhost:8080")

  # Add data
  m.add("Project kickoff notes...", tags=["projects"])

  # Semantic search
  results = m.search("project timeline", mode="hybrid")

  # RAG chat
  answer = m.chat("What are the key milestones?")

  # Knowledge graph
  entities = m.entities(query="people involved")
  related = m.related(entity_id="ent_01ABC...")
  ```

  **TypeScript:**
  ```typescript
  import { MemDog } from 'mem-dog-client';
  const m = new MemDog('http://localhost:8080');

  await m.add('Project kickoff notes...', { tags: ['projects'] });
  const results = await m.search('project timeline', { mode: 'hybrid' });
  ```

  **curl:**
  ```bash
  # Add data
  curl -X POST http://localhost:8080/api/v1/data \
    -H "Content-Type: application/json" \
    -d '{"content": "Meeting notes...", "tags": ["meetings"]}'

  # RAG Chat
  curl -X POST http://localhost:8080/api/v1/ai/query/chat \
    -d '{"query": "What decisions were made?", "search_mode": "hybrid"}'
  ```

- Mention: "Also available in Go, Rust, and Ruby. Full API docs at /docs."

#### Use Cases Section (optional but recommended)
- 3-4 cards showing who mem-dog is for:
  - **AI Engineers:** Build agents with persistent, searchable memory. Use the SDKs or MCP server to give Claude, GPT, or any LLM access to your knowledge base.
  - **Startups:** Replace 3-4 tools (memory SDK + knowledge graph + integration platform + RAG engine) with one self-hosted platform.
  - **Privacy-Conscious Teams:** Run entirely on your infrastructure with local models. No data leaves your servers. BYOK (bring your own keys) for cloud providers.
  - **Personal Knowledge Management:** Automatically capture and enrich data from your daily tools (Slack, email, calendar, GitHub) into a searchable, AI-powered knowledge base.

#### Footer
- Links: GitHub, Documentation, Quick Start, License (Apache 2.0)
- "Built with FastAPI, Next.js, Neo4j, Nango, and Graphiti"

### 2. Docs Page (/docs) -- optional
- Can be a simple redirect to the Mintlify docs site or a page with links to:
  - Quick Start
  - Architecture
  - Core Concepts
  - API Reference
  - SDK Guides (Python, TypeScript, Go, Rust, Ruby)
  - Deployment (Docker, GKE, AWS, Azure, Mac Mini)

---

## Technical Requirements

- **Framework:** Next.js 14 (App Router) with static export, OR Astro -- whichever the builder prefers for a static marketing site
- **Styling:** Tailwind CSS. Dark mode only (no light mode toggle needed).
- **Animations:** Subtle. Use Framer Motion or CSS animations for scroll reveals, hover effects on cards, and the hero section. Nothing flashy.
- **Responsive:** Must look great on mobile, tablet, and desktop
- **Performance:** Static site, should score 95+ on Lighthouse
- **SEO:** Proper meta tags, Open Graph tags, structured data. Title: "mem-dog -- The Private AI Memory Platform"
- **No backend:** This is a static promotional site. No authentication, no database, no API calls.
- **Assets:** Use placeholder images/screenshots where needed. The architecture diagram can be an SVG or rendered from the Mermaid source provided above.

---

## Content Reference

All content for this site comes from the mem-dog repository:

- **README.md** -- Main product description, architecture diagram, feature list, comparison table, quick start
- **docs/comparisons/** -- Detailed comparisons vs mem0, Zep, Dify, etc.
- **docs/features/** -- Deep dives on RAG Chat, Smart Routing, Webhooks, Access Control, MCP Server, Memory Compression, AI Studio, Pod Management
- **docs/core-concepts/** -- Memory types, search modes, knowledge graph, storage backends
- **docs/clients/** -- SDK documentation for all 5 languages

All the content above is accurate and complete -- use it directly. Do not invent features or capabilities not listed here.

---

## Key Differentiators to Emphasize

Throughout the site, make sure these points come through clearly:

1. **All-in-one:** mem-dog replaces mem0 + Zep + Nango + Dify in a single platform
2. **Privacy-first:** Self-hosted, local-first models, data never leaves your infra
3. **Free & open source:** Apache 2.0, no usage fees, no vendor lock-in
4. **Production-ready:** 70+ API endpoints, 5 SDKs, MCP server, Kubernetes manifests, battle-tested on GKE
5. **Temporal knowledge graph:** Not just vector search -- facts have timestamps, relationships are traversable, point-in-time queries work
6. **42-agent pipeline:** Not a single LLM call -- specialized agents for 60+ data types with 5-tier model routing
7. **300+ integrations:** Not API-only -- real app connections with OAuth, token refresh, and encrypted credentials via Nango
