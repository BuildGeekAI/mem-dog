# Example Applications

10 self-contained Python examples in the `examples/` directory demonstrate the mem-dog API across different industries. Each is a single script with inline sample data.

## Prerequisites

```bash
cd clients/python && pip install -e . && cd ../..
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-api-key
```

## Examples by Difficulty

### Beginner

**[01 - Patient Health Journal](../../examples/01_patient_health_journal/)** -- Record symptoms, vitals, and medications. Query with AI and explore medical entities. Uses the simple `MemDog` facade with timeline and user memory.

### Intermediate

**[02 - Legal Case Manager](../../examples/02_legal_case_manager/)** -- Compare all 5 search modes and 4 rerankers side-by-side. Store case documents with factual/episodic memory and knowledge graph.

**[03 - DevOps Incident Tracker](../../examples/03_devops_incident_tracker/)** -- Track incidents with tracing memory, webhooks, and KV store state machine. Run post-mortem analysis with RAG chat.

**[04 - Sales CRM Knowledge Base](../../examples/04_sales_crm_knowledge/)** -- Multi-tenant CRM with organizations, projects, and access-controlled shared memories.

**[08 - Content Publishing Pipeline](../../examples/08_content_publishing/)** -- Multi-channel ingestion via Universal Envelope, duplicate detection with embeddings, editorial workflow via KV store.

**[10 - Team Wiki Lifecycle](../../examples/10_team_wiki/)** -- Full data lifecycle: user onboarding, multi-type memories, compression, GDPR export, bulk cleanup.

### Advanced

**[05 - Research Paper Analyzer](../../examples/05_research_paper_analyzer/)** -- AI viewpoints, analysis templates, citation graphs with semantic memory and graph search.

**[06 - Customer Support Bot](../../examples/06_customer_support_bot/)** -- LangChain adapter for chat history and retrieval, conversation memory with compression, AI skills.

**[07 - Financial Compliance Monitor](../../examples/07_financial_compliance/)** -- Temporal fact queries, document versioning, graph search with time filters, stats dashboard.

**[09 - AI Agent Config Hub](../../examples/09_agent_config_hub/)** -- Full AI configuration surface: agent configs, prompts, skills, engines, model catalog, token usage tracking.

## API Feature Matrix

| Feature | Examples |
|---------|----------|
| Simple facade (`MemDog`) | 01, 03, 04, 06, 10 |
| Full client (`MemDogClient`) | 02-10 |
| LangChain adapter | 06 |
| Timeline memory | 01, 03 |
| Conversation memory | 04, 06, 10 |
| Factual memory | 02, 06, 07 |
| Organizational memory | 02, 04, 07, 10 |
| Semantic memory | 05, 10 |
| Tracing memory | 03 |
| Custom memory | 08, 10 |
| RAG chat | 01, 03, 06 |
| All 5 search modes | 02 |
| All 4 rerankers | 02 |
| Graph search | 05, 07 |
| Temporal facts | 07 |
| Knowledge graph entities | 01, 02, 05 |
| Webhooks | 03 |
| Key-value store | 03, 08 |
| Channels / ingest | 08 |
| Viewpoints | 05 |
| Analysis templates | 05 |
| AI skills | 06, 09 |
| Agent configs | 09 |
| Prompts | 09 |
| Organizations | 04 |
| Access control | 04 |
| User management | 10 |
| Versioning | 07 |
| Memory compression | 06, 10 |
| Bulk operations | 10 |
| Statistics | 07, 09 |
