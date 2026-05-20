# DevOps Incident Tracker

Track system incidents from alert to resolution with tracing memory, webhooks, and state management.

## Features Demonstrated

- **Tracing memory** for distributed trace spans
- **Timeline memory** for event log
- **Webhooks**: create endpoints, list events, view stats
- **Key-value store**: incident state machine (open → investigating → resolved)
- **KV prefix listing** for active incident enumeration
- **RAG chat** for post-mortem analysis

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Sets up webhook endpoints for GitHub deploys and PagerDuty alerts
2. Simulates an incident: creates entry in KV store, logs events to timeline
3. Tracks state transitions: open → investigating → mitigating → resolved
4. Lists all active incidents via KV prefix search
5. Runs post-mortem RAG analysis on the incident timeline
