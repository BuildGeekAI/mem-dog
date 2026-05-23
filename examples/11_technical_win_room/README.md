# Technical Win Room

Sales engineering knowledge base for enterprise deals — POC notes, Slack threads, GitHub issues, and security questionnaires in one searchable, permissioned memory.

## Features Demonstrated

- **Organization & project** scoping for a deal team
- **Memory types**: organizational (deal facts), factual (SE playbook), episodic (POC incidents), timeline (handoff), conversation (war room)
- **Multi-channel artifacts** ingested as tagged data (Slack, GitHub, Gmail, HubSpot)
- **Key-value store** for deal stage (`discovery` → `poc` → `security_review` → `negotiation`)
- **Knowledge graph entities** linking customer, blockers, and commitments
- **Search modes** compared on technical queries (hybrid vs graph vs full)
- **RAG chat** for SE handoff and executive briefings

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Creates a Pre-Sales Engineering org and `deal-acme-corp` project
2. Onboards sales engineers with restricted deal memories
3. Ingests Slack, GitHub, email, and CRM notes for the Acme Corp opportunity
4. Tracks deal stage in the KV store and logs POC incidents as episodic memory
5. Creates graph entities (`Acme Corp`, `SSO`, `POC load test`) for relationship search
6. Compares hybrid, graph, and full search on technical questions
7. Runs RAG chat for handoff scenarios ("What broke in the POC?", "SSO timeline?")
