# Local Development

## Docker Compose

```bash
docker compose up
```

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

For local Kubernetes dev (minikube):

```bash
skaffold dev
```

Port-forwards `api` → :8080, `ui` → :3000. Ingress at `mem-dog.local` / `api.mem-dog.local`.

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
