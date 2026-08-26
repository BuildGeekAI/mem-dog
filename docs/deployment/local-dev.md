# Local Development

## Docker Compose

```bash
docker compose up
```

> **Host ports are overridable.** Every published port in `docker-compose.yml` takes an env
> override with the current value as default — `DB_PORT`, `REDIS_PORT`, `API_PORT`, `UI_PORT`,
> `GATEWAY_PORT`, `MCP_PORT`, `PROCESSOR_PORT`, `NEO4J_HTTP_PORT`, `NEO4J_BOLT_PORT`, and
> `OLLAMA_{SMALL,MEDIUM,LARGE}_PORT`. Use them when another project already holds a port:
> `DB_PORT=55433 docker compose up -d`.

Full `docker compose up` starts **everything**, including Neo4j and 3× Ollama. That needs roughly a **32GB** machine (see [resource-requirements](resource-requirements.mdx)). On a **16GB Mac mini**, use the **lean** profile below instead.

### Profile: lean (≤16GB / Mac mini M2 Pro)

Local stack for ingest / enrich / embeddings / UI / MCP / Graphiti **without** in-cluster Ollama. Use host Ollama or cloud keys for AI. Neo4j is included (1.5 Gi cap); `NEO4J_*` inherits from base compose.

| Service | Port | RAM budget (overlay) |
|---------|------|----------------------|
| `db` | 5432 | 1.5 Gi |
| `redis` | 6379 | 128 Mi |
| `neo4j` | 7474 / 7687 | 1.5 Gi |
| `api` | 8080 | 1 Gi |
| `ui` | 3000 | 768 Mi |
| `mcp-server` | 8091 | 256 Mi |
| `webhook-gateway` | 8070 | 512 Mi |
| `webhook-processor` | 8090 | 3 Gi (room for optional Docling) |

**Document parser:** lean defaults to `DOCUMENT_PARSER=pypdf`. Docling PDF extract is **opt-in** (`DOCUMENT_PARSER=docling`, PDF-only via `docling-slim`). `DOCUMENT_OCR_ENABLED` / `DOCUMENT_HARD_PARSER` are Phase 3 stubs (accepted, not wired yet).

```bash
# Docker Desktop → Resources → Memory: set 10–12 GB (8 GB is too tight)
cp api/.env.example api/.env
# Edit api/.env — for Ollama Cloud embeddings:
#   OLLAMA_CLOUD_API_KEY=...
# (Compose loads api/.env into api, webhook-gateway, and webhook-processor.)

./scripts/dev-lean.sh up -d
# equivalent:
# docker compose -f docker-compose.yml -f docker-compose.lean.yml \
#   up -d db redis neo4j api ui mcp-server webhook-gateway webhook-processor

# Optional Docling PDF path (recreate processor after setting):
# DOCUMENT_PARSER=docling ./scripts/dev-lean.sh up -d webhook-processor
```

Skip: `ollama-*` only. Overlay: [`docker-compose.lean.yml`](../../docker-compose.lean.yml). Related: [`document-parsing-upgrade`](../plans/document-parsing-upgrade.md).

UI: [http://localhost:3000](http://localhost:3000) · API: [http://localhost:8080](http://localhost:8080) · Neo4j: [http://localhost:7474](http://localhost:7474) · MCP SSE: [http://localhost:8091/mcp/sse](http://localhost:8091/mcp/sse) (`x-api-key`).

### Profile: lean on Kubernetes (Docker Desktop)

Two profiles — still **no in-cluster Ollama** (host Metal at `http://host.docker.internal:11434`).

| Profile | Fits | Includes |
|---------|------|----------|
| **`core`** (default) | **~10 GB** | postgres, redis, neo4j, api, ui, mcp, gateway, HTTP ADK processor |
| **`full`** | **12–16 GB** | core base + **NATS pipeline** (receiver / pull-worker / agent) + Nango + Supabase (Kong/GoTrue/PostgREST/**Meta/Realtime/Studio/seed**) + OpenClaw |

#### `core` pods

| Pod | Port-forward | RAM budget |
|-----|--------------|------------|
| `postgres` / `redis` | — | 1.5 Gi / 128 Mi |
| `neo4j` | 7474 | 1.5 Gi |
| `api` / `ui` / `mcp-server` | 8080 / 3000 / 8091 | 1 Gi / 768 Mi / 256 Mi |
| `webhook-gateway` | 8070 | 512 Mi |
| `webhook-processor` (HTTP ADK) | 8090 | 2 Gi |

#### `full` adds / changes

| Pod | Port-forward | Notes |
|-----|--------------|--------|
| `nats` / `webhook-receiver` / `webhook-pull-worker` / `webhook-agent` | 8092 / 8090 | Prod-like pipeline; HTTP processor scaled to **0** |
| `nango-db` / `nango-server` | 3003 | Integrations OAuth |
| Supabase `db`/`kong`/`auth`/`rest`/`meta`/`realtime`/`studio` + seed | 8000 / Studio 54323 | Full self-hosted minus GKE routes; Studio uses `HOSTNAME=0.0.0.0` for port-forward; seed waits for Postgres |
| `openclaw-node` | 18789 | DigiMe (cap 1 Gi) |

**Still skipped vs GKE:** in-cluster Ollama, Gateway HTTPRoutes/ReferenceGrants, KEDA autoscaling.

**Prerequisites:** Docker Desktop Kubernetes, context `docker-desktop`, host Ollama on `:11434` with `embeddinggemma` + `llama3.2:1b`. For `full`, set `GEMINI_API_KEY` in `api/.env` for OpenClaw / gateway / pipeline LLM fallback.

```bash
# ≤10 GB — core only:
./scripts/dev-lean-k8s.sh up              # same as: up core
./scripts/dev-lean-k8s.sh up core --no-build

# 12–16 GB — NATS pipeline + Nango + Supabase + OpenClaw:
./scripts/dev-lean-k8s.sh up full
# (script rolls webhook-gateway + api after apply so ConfigMap env like WEBHOOK_GATEWAY_URL is live)

./scripts/dev-lean-k8s.sh down            # tear down everything
```

Manifests: [`k8s/lean/core/`](../../k8s/lean/core/), [`k8s/lean/full/`](../../k8s/lean/full/). `STORAGE_BACKEND` stays `local`. On `full`, gateway forwards envelopes to the in-cluster receiver (`WEBHOOK_GATEWAY_URL` → NATS path).

Compose lean vs k8s lean:

| | Compose (`dev-lean.sh`) | Kubernetes (`dev-lean-k8s.sh`) |
|--|----------------------|-------------------------------|
| Processor | `LOCAL_DEV` HTTP | `core`: HTTP processor · `full`: NATS + agent |
| Ollama | `host.docker.internal:11434` | Same |
| Postgres / Redis | Compose services | `data` namespace pods |
| Supabase / Nango / OpenClaw | Not in Compose lean | `up full` |
| UI server URL | `http://api:8080` | `http://api.mem-dog.svc.cluster.local:8080` |
| API auth | Usually unset (open) | `API_KEY=dev-local-key`; gateway + processor use matching `MEM_DOG_API_KEY` / `WEBHOOK_API_KEY`; UI build gets `NEXT_PUBLIC_API_KEY` |
| Embeddings | Host Ollama if no cloud key; `OLLAMA_CLOUD` / `SYSTEM_GEMINI` win when set | Same |

### Services (full stack)

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8080 | Core API (`STORAGE_BACKEND=local`) |
| `ui` | 3000 | Next.js frontend |
| `db` | 5432 | PostgreSQL 16 + pgvector |
| `redis` | 6379 | Redis 7 |
| `ollama-small` | 8081 | Small model tier |
| `ollama-medium` | 8082 | Medium model tier |
| `ollama-large` | 8083 | Large model tier |
| `webhook-gateway` | 8070 | Channel adapter gateway |
| `webhook-processor` | 8090 | Local webhook processor (`8090:8080`) |
| `neo4j` | 7474 / 7687 | Graphiti (included in lean; omitted only if you leave it out of `up`) |
| `mcp-server` | 8091 | MCP SSE |

### Differences from production

- `STORAGE_BACKEND=local` — filesystem instead of GCS/Supabase
- `DEPLOYMENT_MODE=local` — Docker container restarts instead of Cloud Run
- `LOCAL_DEV=true` on processor — HTTP trigger instead of NATS
- API mounts Docker socket for Ollama container management
- UI uses Next.js rewrites to proxy `/api/v1/*` (no CORS)
- Lean overlay skips `ollama-*`, caps Neo4j/processor RAM, and sets `OLLAMA_TIER=false` (host Ollama or cloud)

## Skaffold

For minimal local Kubernetes dev (API + UI only):

```bash
skaffold dev
```

Port-forwards `api` → :8080, `ui` → :3000. Ingress at `mem-dog.local` / `api.mem-dog.local`.

For lean on Docker Desktop: `./scripts/dev-lean-k8s.sh up` (core, ≤10GB) or `up full` (NATS pipeline + Nango/Supabase/OpenClaw) — see **Profile: lean on Kubernetes** above.

## Environment Files

| File | Scope |
|------|-------|
| `config/ai.env` | Shared AI model defaults |
| `api/.env` | API-specific overrides |
| `webhook-gateway/.env` | Gateway-specific overrides |

Priority: env var > GCS system config > `.env` > `config/ai.env` > defaults.

## Testing

```bash
# API
cd api && pytest                           # All tests
cd api && pytest tests/test_foo.py -v      # Single file

# Scripts
./scripts/test-api.sh                      # E2E curl tests
./scripts/test-webhook.sh                  # Webhook pipeline tests
./scripts/smoke-api-model-garden.sh        # AI smoke tests

# UI
cd ui && npm run test:unit                 # Jest
cd ui && npm run test:e2e                  # Playwright
```

## URLs

| URL | Description |
|-----|-------------|
| http://localhost:3000 | UI |
| http://localhost:8080 | API |
| http://localhost:8080/docs | API Swagger |
| http://localhost:8070/docs | Gateway Swagger |
