# Local Development

## Docker Compose

```bash
docker compose up
```

### Services

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
| `webhook-processor` | 8090 | Local webhook processor |

### Differences from production

- `STORAGE_BACKEND=local` — filesystem instead of GCS/Supabase
- `DEPLOYMENT_MODE=local` — Docker container restarts instead of Cloud Run
- `LOCAL_DEV=true` on processor — HTTP trigger instead of NATS
- API mounts Docker socket for Ollama container management
- UI uses Next.js rewrites to proxy `/api/v1/*` (no CORS)

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
