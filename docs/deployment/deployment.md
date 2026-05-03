# Deployment

## Targets

| Component | Target | Namespace | Command |
|-----------|--------|-----------|---------|
| **API** | GKE | `memdog` | `deploy-api-gke` |
| **UI** | Cloud Run | -- | `deploy-ui` |
| **Webhook Pipeline** | GKE | `webhook-pipeline` | `deploy-webhook-pipeline-gke` |
| **Webhook Gateway** | GKE | `webhook-gateway` | `deploy-webhook-gateway-gke` |
| **OpenClaw Node** | GKE | `webhook-gateway` | `deploy-openclaw-node-gke` |
| **Neo4j** | GKE | `neo4j` | `kubectl apply -f k8s/neo4j/` |
| **Supabase** | GKE | `supabase` | `deploy-supabase-gke` |

**Project:** `memdog-dev` | **Env:** `dev` | **Cluster:** `open-jaw` (`us-central1-a`)

## Deploy Commands

```bash
# Set cluster context
export GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a

# API -> GKE
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-api-gke -p memdog-dev -e dev

# UI -> Cloud Run (MUST include Supabase env vars)
MEM_DOG_WEBHOOK_GATEWAY_URL="http://<gateway-ip>" \
NEXT_PUBLIC_SUPABASE_ANON_KEY="<anon-key>" \
SUPABASE_AUTH_URL="http://<gateway-ip>" \
./scripts/manual-deploy.sh deploy-ui -p memdog-dev -e dev

# Webhook Pipeline -> GKE
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-webhook-pipeline-gke -p memdog-dev -e dev

# Webhook Gateway -> GKE
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-webhook-gateway-gke -p memdog-dev -e dev

# Neo4j -> GKE (apply manifests directly)
kubectl apply -f k8s/neo4j/

# Full stack
./scripts/manual-deploy.sh deploy-all -p memdog-dev -e dev
```

## GKE Namespaces

### `memdog` -- API

- `api` Deployment (1 replica, PVC at `/data`)
- `api` Service (ClusterIP :8080)
- `api-sa` ServiceAccount (Workload Identity for GCS)
- `api-supabase-secrets` Secret
- `api-config` ConfigMap (STORAGE_BACKEND, RAW_BUCKET, etc.)
- Env vars: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` for Graphiti

### `neo4j` -- Knowledge Graph

- `neo4j` Deployment (Neo4j 5.26 Community + APOC)
- `neo4j` Service (ClusterIP :7687 bolt, :7474 http)
- `neo4j-data` PVC (10Gi)
- `neo4j-auth` Secret

### `webhook-pipeline` -- Data Processing

- `webhook-receiver`, `webhook-pull-worker`, `webhook-agent` Deployments
- `nats` (NATS 2.10, ports 4222 + 8222)
- `ollama` (embedding model), `ollama-chat` (gemma3:4b)

### `webhook-gateway` -- Channel Ingestion

- `webhook-gateway` Deployment
- `openclaw-node` Deployment (DigiMe agent)
- `open-jaws` Gateway (L7 Global External Managed LB)

### `supabase` -- Database Stack

Postgres 16 + pgvector (StatefulSet), PostgREST, GoTrue, Kong, Realtime, Meta, Studio.

## Gateway Routing (`open-jaws`)

| Path | Destination | Timeout |
|------|-------------|---------|
| `/gke-api/*` | `api` service (prefix stripped) | 120s |
| `/oc/*` | `openclaw-node` (prefix stripped) | 30s |
| `/webhooks`, `/channels`, `/query`, `/chat`, `/api`, `/health` | `webhook-gateway` | 30s |

## SQL Migrations

Apply in Supabase SQL Editor or via `psql`:

| Migration | Purpose |
|-----------|---------|
| `api/supabase/mem_dog_blobs.sql` | Blob store table |
| `api/supabase/mem_dog_embeddings.sql` | pgvector embeddings table |
| `api/supabase/mem_dog_graph.sql` | Entity/relationship graph tables |
| `api/supabase/mem_dog_embeddings_fts.sql` | tsvector column + hybrid/FTS search RPCs |
| `api/supabase/organizations.sql` | Org/project hierarchy tables |
| `api/supabase/profiles.sql` | User profiles |
| `api/supabase/agent_configs.sql` | Agent config table |
| `api/supabase/integration_tables.sql` | Integration provider/connection tables |

## Dependency Rules

- Changing webhook agent code (`model_client.py`, `llm_utils.py`, `api_client/`) -> redeploy webhook pipeline
- Changing integration router/models -> redeploy API
- Changing `webhook-gateway/app/credentials.py` -> redeploy webhook gateway
- `NEXT_PUBLIC_*` vars are baked at Docker build time (not runtime)

## Shared Config

- `config/ai.env` -- canonical AI model defaults sourced by all deploy scripts
- `SYSTEM_CONFIG_BUCKET` -- optional GCS bucket for `platform-config.json` (overrides all config at runtime)

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `test-api.sh` | E2E curl test suite |
| `test-webhook.sh` | Webhook pipeline tests |
| `smoke-api-model-garden.sh` | AI endpoint smoke tests |
| `seed-demo-user.sh` | Seed demo user |
| `wipe-user-data.sh` | Wipe user data |
| `drop-all-data.sh` | Drop all data |
| `system-config.sh` | Manage GCS system config |
