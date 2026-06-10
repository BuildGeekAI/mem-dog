# mem-dog + Nango: How They Work Together

**Last updated:** March 2026

mem-dog uses Nango as its integration backend. Nango handles OAuth flows, token refresh, credential encryption, and the provider catalog. mem-dog adds the intelligence layer on top — 40 AI agents, 5 search modes, knowledge graph, per-user webhook endpoints, and temporal reasoning.

---

## Architecture

```
mem-dog (private AI memory platform)
  │
  ├── Webhook Gateway (per-user webhooks, channel normalization)
  ├── API (70+ endpoints, storage, search, AI config)
  ├── Webhook Pipeline (40 agents, NATS, LLM enrichment)
  ├── Supabase (pgvector, BM25, auth)
  ├── Neo4j/Graphiti (temporal knowledge graph)
  │
  └── Nango (integration backend)  ← self-hosted in nango namespace
        ├── OAuth2 flows (authorization, code exchange, callbacks)
        ├── Automatic token refresh (before expiry)
        ├── AES-256-GCM credential encryption
        ├── 300+ provider templates (community-maintained)
        └── Connection management (per end_user_id)
```

## What Nango Handles

| Capability | Details |
|-----------|---------|
| **OAuth2 flows** | Full authorization code grant, PKCE, state management |
| **Token refresh** | Automatic — no background task, no 401 retry needed |
| **Credential encryption** | AES-256-GCM with `NANGO_ENCRYPTION_KEY` |
| **Provider catalog** | 300+ community-maintained templates with OAuth URLs, scopes, proxy config |
| **Connection management** | Per-user connections tagged with `end_user_id` |
| **Connect UI** | Embeddable auth widget (port 3009) |

## What mem-dog Adds on Top

| Capability | Details |
|-----------|---------|
| **Per-user webhook endpoints** | `whk_<ulid>` with CRUD, stats, events, HMAC secrets |
| **Channel normalization** | 25+ channel adapters → UniversalEnvelope format |
| **AI enrichment** | 40 typed agents classify, analyze, embed, extract entities |
| **Knowledge graph** | Dual-layer: Postgres + Graphiti/Neo4j with temporal facts |
| **Multi-signal search** | 5 modes (vector, FTS, hybrid, graph, full) + 4 rerankers |
| **RAG chat** | Conversational Q&A with inline [1][2] citations |
| **Memory system** | 10 types with TTL, ACLs, versioning, project scoping |
| **Channel affinity tagging** | Tags connections by relevance to inbound webhook channel |
| **Response normalization** | `?normalize=contact\|calendar_event` transforms on proxy responses |
| **App category mapping** | 15 unified categories synthesized from Nango metadata |

## Why Nango (Instead of Custom)

mem-dog originally had a custom integration platform (3,945-line provider seed, Fernet encryption, manual OAuth flows, proactive token refresh task). Replacing it with Nango:

- **Deleted ~4,360 lines** of custom OAuth/credential code
- **Automatic token refresh** — eliminates retry logic and background tasks
- **Community-maintained providers** — no more manual seed file updates
- **Battle-tested OAuth** — handles edge cases (PKCE, state management, error recovery)
- **Single responsibility** — Nango does integrations, mem-dog does AI

## Deployment

Nango runs self-hosted in the `nango` GKE namespace alongside mem-dog's other services:

```bash
kubectl apply -f k8s/nango/  # namespace, postgres, nango-server, config, secrets
```

The API and webhook gateway communicate with Nango via in-cluster DNS: `nango-server.nango.svc.cluster.local:3003`.

## Compared to Standalone Nango

If you only need API integrations (OAuth, sync, proxy), standalone Nango is the right choice. mem-dog is for when you need integrations **plus** AI enrichment, knowledge graph, semantic search, and memory — a complete private AI memory platform.
