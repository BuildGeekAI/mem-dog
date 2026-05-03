# Deploying mem-dog on a Mac Mini

Two deployment modes: **local-only** (Docker Compose, no cloud) and **GKE** (Mac Mini as build/deploy machine pushing to Google Cloud).

---

## Option A — Local Only (Docker Compose)

Everything runs on the Mac Mini. No cloud account needed.

### Prerequisites

```bash
# Docker Desktop (provides Docker + buildx + compose)
brew install --cask docker

# Start Docker Desktop, then verify
docker info
```

### Deploy

```bash
git clone https://github.com/BuildGeekAI/mem-dog.git
cd mem-dog
docker compose up
```

That starts 11 services:

| Service | Port | Description |
|---------|------|-------------|
| **API** | 8080 | Core API (`STORAGE_BACKEND=local`) |
| **UI** | 3000 | Next.js frontend |
| **MCP Server** | 8091 | MCP SSE endpoint (8 tools) |
| **Webhook Gateway** | 8070 | Channel adapter + LiteLLM |
| **Webhook Processor** | 8090 | Local AI pipeline (HTTP trigger) |
| **PostgreSQL + pgvector** | 5432 | Structured data + embeddings |
| **Redis** | 6379 | Cache |
| **Neo4j** | 7474 / 7687 | Knowledge graph (Graphiti) |
| **Ollama Small** | 8081 | Gemma3 4b |
| **Ollama Medium** | 8082 | Gemma3 12b |
| **Ollama Large** | 8083 | Gemma3 27b |

### Access

| What | URL |
|------|-----|
| UI | http://localhost:3000 |
| API docs | http://localhost:8080/docs |
| Gateway docs | http://localhost:8070/docs |
| MCP SSE endpoint | http://localhost:8091/mcp/sse |
| Neo4j browser | http://localhost:7474 |

### Connect Claude Desktop (local)

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mem-dog": {
      "url": "http://localhost:8091/mcp/sse"
    }
  }
}
```

No API key needed locally (auth is disabled in local mode).

### LLM Configuration

By default, the pipeline uses local Ollama models (no API keys needed). For better quality, set environment variables before `docker compose up`:

```bash
# Use Gemini for the webhook gateway
export GEMINI_API_KEY="AIza..."
export LLM_PROVIDER=gemini

docker compose up
```

Or create a `.env` file in the repo root:

```env
GEMINI_API_KEY=AIza...
LLM_PROVIDER=gemini
```

### GPU Acceleration (Apple Silicon)

Ollama in Docker doesn't use Apple Metal GPU. For GPU-accelerated inference, run Ollama natively:

```bash
# Install Ollama natively
brew install ollama
ollama serve &
ollama pull gemma3:4b

# Point docker-compose services at native Ollama
export MODEL_SERVER_URL_SMALL=http://host.docker.internal:11434
export MODEL_SERVER_URL_MEDIUM=http://host.docker.internal:11434
export MODEL_SERVER_URL_LARGE=http://host.docker.internal:11434
docker compose up
```

### Expose to LAN

To access from other machines on your network (e.g., connect Claude Desktop on your laptop to the Mac Mini):

```bash
# Find Mac Mini IP
ipconfig getifaddr en0

# Access from other machines:
# UI:  http://<mac-mini-ip>:3000
# MCP: http://<mac-mini-ip>:8091/mcp/sse
```

Claude Desktop config on your laptop:

```json
{
  "mcpServers": {
    "mem-dog": {
      "url": "http://<mac-mini-ip>:8091/mcp/sse"
    }
  }
}
```

### Expose to Internet (optional)

For external access without a cloud deployment:

```bash
# Option 1: Tailscale (recommended, free for personal use)
brew install --cask tailscale
# Sign in, then use Tailscale IP/MagicDNS

# Option 2: ngrok (quick tunnels)
brew install ngrok
ngrok http 8091  # Tunnel MCP server
ngrok http 3000  # Tunnel UI (separate terminal)

# Option 3: Cloudflare Tunnel (free, persistent)
brew install cloudflared
cloudflared tunnel create mem-dog
cloudflared tunnel route dns mem-dog mcp.yourdomain.com
cloudflared tunnel run --url http://localhost:8091 mem-dog
```

### Data Persistence

Data persists in Docker volumes:

```bash
# List volumes
docker volume ls | grep mem-dog

# Volumes:
#   mem-dog-data       — API data (local filesystem storage)
#   pgdata             — PostgreSQL (metadata, embeddings, memories)
#   neo4j-data         — Neo4j knowledge graph
#   ollama-*-data      — Downloaded model weights
```

To reset everything:

```bash
docker compose down -v  # -v removes volumes (destroys all data)
```

### Differences from GKE

| | Local | GKE |
|---|---|---|
| Storage | Local filesystem | Supabase + GCS |
| Auth | Disabled (no JWT) | Supabase GoTrue + API keys |
| Pipeline | HTTP trigger (sync) | NATS JetStream (async) |
| Models | Ollama in Docker (no GPU) | Ollama on GKE nodes |
| MCP auth | No key needed | `md_*` API key required |
| SSL | None (HTTP) | Via Gateway (can add cert) |

---

## Option B — GKE (Mac Mini as Deploy Machine)

The Mac Mini builds Docker images and deploys them to GKE. Production workloads run on Google Cloud.

### Prerequisites

```bash
# Tools
brew install --cask google-cloud-sdk docker
gcloud components install kubectl gke-gcloud-auth-plugin
curl -LsSf https://astral.sh/uv/install.sh | sh
brew install node@20 jq

# Authenticate
gcloud auth login
gcloud auth application-default login
gcloud config set project memdog-dev
gcloud auth configure-docker us-central1-docker.pkg.dev

# Enable APIs
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  --project=memdog-dev
```

### Create GKE Cluster (first time only)

```bash
gcloud container clusters create open-jaw \
  --zone=us-central1-a \
  --num-nodes=3 \
  --machine-type=e2-standard-4 \
  --disk-size=50 \
  --enable-ip-alias \
  --workload-pool=memdog-dev.svc.id.goog \
  --gateway-api=standard \
  --project=memdog-dev

gcloud container clusters get-credentials open-jaw \
  --zone=us-central1-a --project=memdog-dev
```

### Deploy Everything

Run these from the repo root on the Mac Mini. Order matters for first-time setup:

```bash
export GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a

# 1. Supabase (database + auth — everything depends on this)
./scripts/manual-deploy.sh deploy-supabase-gke -p memdog-dev -e dev

# 2. API (storage, search, auth middleware)
./scripts/manual-deploy.sh deploy-api-gke -p memdog-dev -e dev

# 3. Webhook Pipeline (NATS + 40 AI agents + Ollama)
./scripts/manual-deploy.sh deploy-webhook-pipeline-gke -p memdog-dev -e dev

# 4. Webhook Gateway (channel adapter, creates the L7 gateway)
./scripts/manual-deploy.sh deploy-webhook-gateway-gke -p memdog-dev -e dev

# 5. MCP Server (SSE transport for Claude Desktop / Cursor)
./scripts/manual-deploy.sh deploy-mcp-server-gke -p memdog-dev -e dev

# 6. OpenClaw Node / DigiMe (optional — conversational AI agent)
./scripts/manual-deploy.sh deploy-openclaw-node-gke -p memdog-dev -e dev

# 7. UI (Cloud Run — needs gateway IP + Supabase keys)
GATEWAY_IP=$(kubectl get gateway open-jaws -n webhook-gateway -o jsonpath='{.status.addresses[0].value}')
ANON_KEY=$(kubectl get secret supabase-secrets -n supabase -o jsonpath='{.data.ANON_KEY}' | base64 -d)

MEM_DOG_WEBHOOK_GATEWAY_URL="http://$GATEWAY_IP" \
NEXT_PUBLIC_SUPABASE_ANON_KEY="$ANON_KEY" \
SUPABASE_AUTH_URL="http://$GATEWAY_IP" \
./scripts/manual-deploy.sh deploy-ui -p memdog-dev -e dev
```

### Verify

```bash
GATEWAY_IP=$(kubectl get gateway open-jaws -n webhook-gateway -o jsonpath='{.status.addresses[0].value}')

# All pods
kubectl get pods -n mem-dog
kubectl get pods -n webhook-pipeline
kubectl get pods -n webhook-gateway
kubectl get pods -n supabase

# Health checks
curl http://$GATEWAY_IP/gke-api/health    # API
curl http://$GATEWAY_IP/health            # Gateway
curl http://$GATEWAY_IP/auth/v1/health    # Supabase Auth

# MCP server
curl http://$GATEWAY_IP/mcp/health
```

### Connect Claude Desktop (GKE)

```json
{
  "mcpServers": {
    "mem-dog": {
      "url": "http://<GATEWAY_IP>/mcp/sse",
      "headers": {
        "x-api-key": "md_your_api_key"
      }
    }
  }
}
```

Get your API key from the UI (Settings > API Keys) or create one:

```bash
curl -X POST http://$GATEWAY_IP/gke-api/api/v1/users/<user_id>/api-keys \
  -H "Content-Type: application/json" \
  -d '{"name": "claude-desktop"}'
```

### GKE Architecture

```
                    Cloud Run (UI)
                    Next.js + rewrites
                         |
                         v
  ┌──────────────────────────────────────────────────────┐
  │              open-jaws Gateway (L7 LB)               │
  │               External IP: <GATEWAY_IP>              │
  ├──────────┬────────────┬──────────┬──────────┬────────┤
  │ /gke-api │ /webhooks  │  /mcp/*  │  /oc/*   │/auth/* │
  │    ↓     │ /channels  │    ↓     │    ↓     │   ↓    │
  │   API    │     ↓      │   MCP    │ DigiMe   │GoTrue  │
  │(mem-dog) │  Gateway   │  Server  │  Agent   │(supa)  │
  └──────────┴─────┬──────┴──────────┴──────────┴────────┘
                   │
                   v
          Webhook Pipeline (NATS + 40 agents + Ollama)
                   │
                   v
          Supabase (Postgres + pgvector + GoTrue + Kong)
```

### Namespaces

| Namespace | Components |
|-----------|-----------|
| `mem-dog` | API, MCP Server |
| `webhook-pipeline` | NATS, agents, Ollama |
| `webhook-gateway` | Gateway, DigiMe, `open-jaws` LB |
| `supabase` | PostgreSQL, PostgREST, GoTrue, Kong |

### Redeploy a Single Component

```bash
export GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a

# API only
./scripts/manual-deploy.sh deploy-api-gke -p memdog-dev -e dev

# MCP server only
./scripts/manual-deploy.sh deploy-mcp-server-gke -p memdog-dev -e dev

# UI only
MEM_DOG_WEBHOOK_GATEWAY_URL="http://$GATEWAY_IP" \
NEXT_PUBLIC_SUPABASE_ANON_KEY="$ANON_KEY" \
SUPABASE_AUTH_URL="http://$GATEWAY_IP" \
./scripts/manual-deploy.sh deploy-ui -p memdog-dev -e dev
```

### Logs

```bash
kubectl logs -n mem-dog deployment/api -f --tail=50
kubectl logs -n mem-dog deployment/mcp-server -f --tail=50
kubectl logs -n webhook-gateway deployment/webhook-gateway -f --tail=50
kubectl logs -n webhook-pipeline deployment/webhook-agent -f --tail=50
```

### Restart All

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh restart-gke -p memdog-dev -e dev
```

---

## Pre-flight Resource Check

Before deploying, run the preflight script to see if your machine has enough resources:

```bash
# Check local Docker Compose requirements (default: full profile)
./scripts/preflight-check.sh

# Check with a specific profile
./scripts/preflight-check.sh --profile minimal    # API + UI + Postgres only
./scripts/preflight-check.sh --profile standard   # Full stack, cloud LLMs
./scripts/preflight-check.sh --profile full        # Everything + local Ollama

# Check GKE cluster capacity
./scripts/preflight-check.sh --gke
./scripts/preflight-check.sh --gke --profile standard
```

### Resource Matrix

| Profile | Components | Min RAM | Min CPU | Best for |
|---------|-----------|---------|---------|----------|
| **minimal** | 3 (API, UI, Postgres) | 4 GB | 2 cores | Dev/testing, no AI pipeline |
| **standard** | 16 (+ gateway, pipeline, Supabase, Redis) | 12 GB | 4 cores | Full stack with cloud LLMs (Gemini) |
| **full** | 23 (+ Ollama x3, Neo4j, Nango, OpenClaw) | 24 GB | 8 cores | Everything including local models |

### Per-Component Resources (K8s requests / limits)

| Component | CPU Request | Mem Request | CPU Limit | Mem Limit |
|-----------|------------|-------------|-----------|-----------|
| API | 100m | 256Mi | 1000m | 1Gi |
| PostgreSQL + pgvector | 250m | 512Mi | 1000m | 1Gi |
| Webhook Gateway | 100m | 128Mi | 500m | 256Mi |
| Webhook Agent (40 sub-agents) | 50m | 128Mi | 500m | 512Mi |
| NATS | 25m | 64Mi | 200m | 128Mi |
| Ollama Embedding (embeddinggemma) | 50m | 768Mi | 500m | 2Gi |
| Ollama Chat (gemma3:4b) | 100m | 1Gi | 2000m | 4Gi |
| Ollama Large (gemma3:27b) | 200m | 2Gi | 4000m | 8Gi |
| Neo4j | 250m | 512Mi | 500m | 1Gi |
| OpenClaw Node | 50m | 512Mi | 2000m | 4Gi |
| Supabase (all 6 pods) | 550m | 832Mi | 2750m | 1.6Gi |
| Nango (server + DB) | 200m | 512Mi | 1000m | 1Gi |

### Ollama Model Sizes

| Model | RAM at Runtime | Disk Download |
|-------|---------------|---------------|
| embeddinggemma | ~1 GB | 1.6 GB |
| gemma3:4b | ~4 GB | 3.3 GB |
| gemma3:12b | ~8 GB | 8.1 GB |
| gemma3:27b | ~16 GB | 17.0 GB |
| qwen3-vl | ~4 GB | 5.5 GB |

### Mac Mini Recommendations

| Mac Mini Model | RAM | Profile | Notes |
|---------------|-----|---------|-------|
| M1 8GB | 8 GB | minimal | API + UI only, use Gemini for AI |
| M1 16GB | 16 GB | standard | Full stack, cloud LLMs, no large Ollama |
| M2 Pro 32GB | 32 GB | full | All services + gemma3:4b + embedding |
| M2 Pro/Max 64GB | 64 GB | full | All services + all Ollama models incl. 27b |

---

## Cost Comparison

| | Local (Docker Compose) | GKE |
|---|---|---|
| **Cloud cost** | $0 | ~$150-300/mo (3x e2-standard-4 + Cloud Run) |
| **LLM cost** | $0 (local Ollama) | $0 (Ollama on GKE) or ~$5-20/mo (Gemini API) |
| **Hardware** | Mac Mini (M1+ recommended, 16GB+ RAM) | Any machine with Docker + gcloud |
| **External access** | Tailscale/ngrok/Cloudflare | Gateway IP (public) |
| **Auth** | None | Supabase JWT + API keys |
| **Best for** | Personal use, dev, testing | Teams, production, multi-user |
