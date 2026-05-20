# mem-dog Example Applications

10 self-contained Python examples demonstrating the mem-dog API across different industries. Each example is a single script with inline sample data — no external dependencies beyond the SDK.

## Quick Start

```bash
# Install the SDK
cd clients/python && pip install -e . && cd ../..

# Set environment
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-api-key

# Run any example
python examples/01_patient_health_journal/main.py
```

For example 06 (Customer Support Bot), install the LangChain adapter:
```bash
pip install -e "clients/python[langchain]"
```

## Examples

| # | Name | Industry | Difficulty | Key Features |
|---|------|----------|-----------|-------------|
| [01](01_patient_health_journal/) | Patient Health Journal | Healthcare | Beginner | Timeline memory, RAG chat, entity search |
| [02](02_legal_case_manager/) | Legal Case Manager | Legal | Intermediate | All 5 search modes + 4 rerankers, knowledge graph |
| [03](03_devops_incident_tracker/) | DevOps Incident Tracker | SRE | Intermediate | Tracing memory, webhooks, KV store, timeline queries |
| [04](04_sales_crm_knowledge/) | Sales CRM Knowledge Base | Sales | Intermediate | Organizations, projects, access control, shared memories |
| [05](05_research_paper_analyzer/) | Research Paper Analyzer | Academic | Advanced | Viewpoints, analysis templates, citation graph |
| [06](06_customer_support_bot/) | Customer Support Bot | Support | Advanced | LangChain adapter, conversation memory, compression |
| [07](07_financial_compliance/) | Financial Compliance Monitor | Finance | Advanced | Temporal facts, versioning, graph search, stats |
| [08](08_content_publishing/) | Content Publishing Pipeline | Media | Intermediate | Channels, ingest, embeddings, tags, KV workflow |
| [09](09_agent_config_hub/) | AI Agent Config Hub | AI/ML | Advanced | Agent configs, prompts, skills, model catalog |
| [10](10_team_wiki/) | Team Wiki Lifecycle | Knowledge Mgmt | Intermediate | User management, bulk ops, memory lifecycle |

## Feature Coverage

Each example focuses on different API areas to collectively demonstrate the full platform:

- **Memory Types**: timeline (01), factual/episodic (02), tracing (03), organizational (04), semantic (05), conversation (06), custom (08), session (10)
- **Search**: RAG chat (01, 03, 06), all 5 modes compared (02), graph/temporal (05, 07), hybrid (03, 04)
- **Knowledge Graph**: entities (01, 02, 05), relationships (02, 05), temporal facts (07)
- **Infrastructure**: webhooks (03), channels/ingest (08), KV store (03, 08)
- **AI Config**: viewpoints (05), analysis templates (05), skills (06, 09), agent configs (09), prompts (09)
- **Multi-tenant**: organizations (04), projects (04), access control (04), users/API keys (10)
- **Lifecycle**: versioning (07), compression (06, 10), bulk delete (10), data export (10)
