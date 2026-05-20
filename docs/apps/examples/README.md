# Example Applications

Complete, runnable example applications demonstrating the mem-dog API across 10 different industries. Each example is a self-contained Python script with inline sample data.

Source code: [`examples/`](../../../examples/)

## Setup

```bash
cd clients/python && pip install -e . && cd ../..
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-api-key
python examples/01_patient_health_journal/main.py
```

## Applications

### Healthcare: Patient Health Journal

**Directory:** `examples/01_patient_health_journal/`

Records daily symptoms, vitals, and medication. Uses **timeline memory** to organize entries chronologically and **RAG chat** to answer questions like "When did my headaches start?" Demonstrates the simple `MemDog` facade — `add()`, `search()`, `get()`, `entities()`, and `related()`.

**API Features:** timeline memory, user memory, RAG search, entity extraction, tags

---

### Legal: Case Manager

**Directory:** `examples/02_legal_case_manager/`

Stores case documents, witness statements, and legal precedents. The highlight is a **side-by-side comparison of all 5 search modes** (vector, fts, hybrid, graph, full) **and all 4 rerankers** (none, rrf, mmr, cross-encoder) on the same query. Uses **factual memory** for precedents and **episodic memory** for case timelines.

**API Features:** 5 search modes, 4 rerankers, factual/episodic memory, batch entity creation, relationship traversal, tags

---

### SRE: DevOps Incident Tracker

**Directory:** `examples/03_devops_incident_tracker/`

Tracks incidents from alert to resolution. Stores trace spans in **tracing memory**, creates **webhook endpoints** for GitHub/PagerDuty, and uses the **key-value store** as a state machine for incident lifecycle (open → investigating → mitigating → resolved). Runs a **RAG post-mortem** when the incident closes.

**API Features:** tracing memory, timeline memory, webhooks (create, list, stats), KV store (set, get, prefix list), RAG chat

---

### Sales: CRM Knowledge Base

**Directory:** `examples/04_sales_crm_knowledge/`

Multi-tenant CRM with **organization hierarchy** (org → members → projects). Stores deal notes in **conversation memory** with restricted access, competitive intel in **organizational memory** with shared access. Demonstrates **access control checks** between team members.

**API Features:** organizations (CRUD, members, roles), projects, access control (shared/restricted/private), conversation memory, organizational memory, user memory

---

### Academic: Research Paper Analyzer

**Directory:** `examples/05_research_paper_analyzer/`

Ingests research papers and generates multiple **AI viewpoints** per paper (Key Findings, Methodology, Limitations). Defines custom **analysis templates** and builds a **citation knowledge graph** with authors and institutions as entities.

**API Features:** viewpoints (create, list, history), analysis templates (create, seed, list), semantic memory, batch entity creation, graph search, knowledge graph traversal

---

### Support: Customer Support Bot

**Directory:** `examples/06_customer_support_bot/`

Multi-turn chatbot with FAQ knowledge base. Shows the **LangChain adapter** pattern (`MemDogChatMessageHistory`, `MemDogRetriever`), **conversation memory** with TTL, **memory compression** for old chats, and **AI skill** registration.

**Prerequisites:** `pip install mem-dog-client[langchain]`

**API Features:** LangChain adapter, conversation memory, factual memory (FAQ), user memory (preferences), RAG chat with history, memory compression, AI skills

---

### Finance: Compliance Monitor

**Directory:** `examples/07_financial_compliance/`

Tracks regulatory filings with **temporal awareness**. Queries point-in-time facts ("What was the threshold in Q2 2025?"), shows **document versioning** (update → list versions → get specific version), and builds a **compliance dashboard** from platform statistics.

**API Features:** temporal facts (query_facts, get_fact_timeline), document versioning (update_data, list_versions, get_version), graph search with temporal_filter, organizational memory (no_expiry), stats (global, data, memory)

---

### Media: Content Publishing Pipeline

**Directory:** `examples/08_content_publishing/`

Multi-channel content pipeline. Registers **channel identities** (slack, email, cms), ingests articles via the **Universal Envelope** format, detects duplicates using **embeddings**, and manages editorial workflow through the **KV store** (draft → review → published).

**API Features:** channels (create identity, list, update), ingest (Universal Envelope), embeddings (create, retrieve), tags (add, remove, search), KV store (workflow state), custom memory

---

### AI/ML: Agent Configuration Hub

**Directory:** `examples/09_agent_config_hub/`

Complete AI infrastructure management. Browses the **model catalog**, configures **AI engines**, creates a **prompt library**, registers **AI skills**, sets up **agent configs** with resolution, and tracks **token usage** for cost management.

**API Features:** model catalog (list, details), AI engines (CRUD), prompts (CRUD), skills (CRUD), agent configs (CRUD, resolve), token usage (record, get), agent type counts, system config, AI health check

---

### Knowledge Management: Team Wiki Lifecycle

**Directory:** `examples/10_team_wiki/`

Full data lifecycle demonstration. **Onboards users** with API keys, seeds content across **5 memory types** (session, conversation, organizational, semantic, custom), **filters and lists** memories, **compresses** stale content, **exports** user data for GDPR, and **bulk deletes** expired items.

**API Features:** user management (create, API keys), 5 memory types with TTLs, memory filtering (type, category, expired), memory compression, data export (dump_user_data), bulk operations (delete data, delete memories), data reorganization
