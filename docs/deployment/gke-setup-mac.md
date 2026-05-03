# Deploying Mem-Dog on GKE from a Mac Mini

End-to-end guide for deploying the full Mem-Dog stack to Google Kubernetes Engine from a Mac Mini (Apple Silicon or Intel).

---

## Prerequisites

### 1. Install Tools

```bash
# Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Google Cloud CLI
brew install --cask google-cloud-sdk

# Docker Desktop (provides docker + buildx)
brew install --cask docker

# kubectl (via gcloud)
gcloud components install kubectl
gcloud components install gke-gcloud-auth-plugin

# uv (Python package manager — used by deploy script)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js 20 (for UI development/testing)
brew install node@20

# jq (optional, for utility scripts)
brew install jq
```

### 2. Authenticate with GCP

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project memdog-dev
```

### 3. Enable Required APIs

```bash
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  certificatemanager.googleapis.com \
  iam.googleapis.com \
  --project=memdog-dev
```

### 4. Create Artifact Registry

```bash
gcloud artifacts repositories create memdog \
  --repository-format=docker \
  --location=us-central1 \
  --project=memdog-dev
```

Configure Docker to push to it:

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## Step 1 — Create the GKE Cluster

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
```

Key flags:
- `--workload-pool` enables Workload Identity (used by API and webhook pipeline for GCS access)
- `--gateway-api=standard` installs the Gateway API CRDs and GKE Gateway Controller (required for the `open-jaws` L7 load balancer)

Get credentials for `kubectl`:

```bash
gcloud container clusters get-credentials open-jaw \
  --zone=us-central1-a \
  --project=memdog-dev
```

Verify:

```bash
kubectl cluster-info
kubectl get nodes
```

---

## Step 2 — Deploy Supabase

Self-hosted Supabase provides PostgreSQL + pgvector, PostgREST, GoTrue (auth), Kong (API gateway), Realtime, Meta, and Studio.

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-supabase-gke -p memdog-dev -e dev
```

This command:
- Creates the `supabase` namespace
- Generates JWT secret, anon key, and service role key (stored in `supabase-secrets`)
- Deploys PostgreSQL StatefulSet with pgvector extension
- Deploys PostgREST, GoTrue, Kong, Realtime, Meta, Studio
- Seeds the database with memdog tables and schema

Verify:

```bash
kubectl get pods -n supabase
# All pods should be Running
```

### Set Up Google OAuth (optional)

If you want Google sign-in:

1. Go to [Google Cloud Console → APIs & Credentials](https://console.cloud.google.com/apis/credentials?project=memdog-dev)
2. Create an **OAuth 2.0 Client ID** (Web application)
3. Add authorized redirect URI: `https://<YOUR_UI_URL>/auth/v1/callback`
4. Add authorized JavaScript origin: `https://<YOUR_UI_URL>`

Then create the secret:

```bash
kubectl create secret generic supabase-auth-oauth -n supabase \
  --from-literal=GOOGLE_CLIENT_ID="<your-client-id>.apps.googleusercontent.com" \
  --from-literal=GOOGLE_CLIENT_SECRET="<your-client-secret>"

kubectl rollout restart deployment/supabase-auth -n supabase
```

---

## Step 3 — Deploy the API

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-api-gke -p memdog-dev -e dev
```

This command:
- Builds the API Docker image (`api/Dockerfile`) for `linux/amd64`
- Pushes to Artifact Registry
- Creates the `memdog` namespace
- Sets up Workload Identity (GSA + KSA binding)
- Creates secrets (API key, Supabase credentials) and configmaps
- Deploys the API with a PVC for local storage
- Creates HTTPRoute for the `open-jaws` gateway at `/gke-api/*`

Verify:

```bash
kubectl get pods -n memdog
kubectl logs -n memdog deployment/api --tail=20
```

---

## Step 4 — Deploy the Webhook Pipeline

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-webhook-pipeline-gke -p memdog-dev -e dev
```

This command:
- Builds 3 Docker images: webhook-receiver, webhook-agent, webhook-pull-worker
- Creates the `webhook-pipeline` namespace
- Deploys NATS 2.10 (message bus)
- Deploys Ollama instances (embedding + chat models)
- Deploys the webhook receiver, agent (40 sub-agents), and pull worker
- Sets up Workload Identity for GCS access

Verify:

```bash
kubectl get pods -n webhook-pipeline
# Should see: nats, ollama, ollama-chat, webhook-receiver, webhook-agent, webhook-pull-worker
```

---

## Step 5 — Deploy the Webhook Gateway

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-webhook-gateway-gke -p memdog-dev -e dev
```

This command:
- Builds the webhook-gateway Docker image
- Creates the `webhook-gateway` namespace
- Deploys the `open-jaws` Gateway (GKE L7 Global External Managed LB)
- Creates HTTPRoutes for `/webhooks`, `/channels`, `/query`, `/chat`, etc.
- Allocates a static external IP address

After deployment, get the gateway IP:

```bash
kubectl get gateway open-jaws -n webhook-gateway -o jsonpath='{.status.addresses[0].value}'
```

Save this IP — it's used by the UI deployment and is the entry point for all external traffic.

Verify:

```bash
kubectl get pods -n webhook-gateway
curl http://<GATEWAY_IP>/health
```

---

## Step 6 — Deploy OpenClaw Node (DigiMe Agent)

Optional — only needed if you want the DigiMe multi-channel AI assistant.

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-openclaw-node-gke -p memdog-dev -e dev
```

This deploys into the `webhook-gateway` namespace alongside the gateway. It requires:
- Secret `openclaw-node-secrets` with `GEMINI_API_KEY`, `MEM_DOG_API_KEY`, `OPENCLAW_GATEWAY_TOKEN`
- PVC `openclaw-home` for persistent storage
- Skills ConfigMap for DigiMe capabilities

Verify:

```bash
kubectl get pods -n webhook-gateway -l app=openclaw-node
```

---

## Step 7 — Deploy the UI (Cloud Run)

The UI deploys to Cloud Run, not GKE. It requires Supabase env vars baked in at build time.

Get the Supabase anon key:

```bash
kubectl get secret supabase-secrets -n supabase -o jsonpath='{.data.ANON_KEY}' | base64 -d
```

Deploy:

```bash
NEXT_PUBLIC_SUPABASE_ANON_KEY="<anon-key-from-above>" \
SUPABASE_AUTH_URL="http://<GATEWAY_IP>" \
./scripts/manual-deploy.sh deploy-ui -p memdog-dev -e dev
```

**Why these env vars matter:**
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Baked into the JS bundle at build time. Controls whether the login page shows. Without it, auth is disabled.
- `SUPABASE_AUTH_URL` — Enables the Next.js server-side rewrite `/auth/v1/*` → GoTrue via the gateway IP. Without it, Supabase auth API calls fail.
- `NEXT_PUBLIC_SUPABASE_URL` is intentionally omitted so the client uses `window.location.origin` and hits the Next.js rewrite proxy (avoids HTTPS→HTTP mixed content).

Verify:

```bash
# The deploy script prints the Cloud Run URL at the end
curl https://<CLOUD_RUN_URL>
```

---

## Step 8 — Verify the Full Stack

### Check all pods

```bash
kubectl get pods -n memdog
kubectl get pods -n webhook-pipeline
kubectl get pods -n webhook-gateway
kubectl get pods -n supabase
```

### Check gateway routing

```bash
GATEWAY_IP=$(kubectl get gateway open-jaws -n webhook-gateway -o jsonpath='{.status.addresses[0].value}')

# API health
curl http://$GATEWAY_IP/gke-api/health

# Gateway health
curl http://$GATEWAY_IP/health

# Supabase auth health
curl http://$GATEWAY_IP/auth/v1/health
```

### Check the UI

Open the Cloud Run URL in a browser. You should see the landing page with login.

### Test the data flow

```bash
# Use the test scripts
./scripts/test-api.sh
./scripts/test-webhook.sh
```

---

## Architecture Overview

```
                    ┌─────────────────────────────────┐
                    │         Cloud Run (UI)           │
                    │     Next.js 14 + Rewrites        │
                    └──────────┬──────────────────────-┘
                               │ /api/v1/* → GKE API
                               │ /auth/v1/* → GoTrue
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   open-jaws Gateway (L7 LB)                  │
│                     External IP: 34.36.80.165                │
├──────────┬─────────────────┬─────────────────┬───────────────┤
│ /gke-api │   /webhooks     │     /oc/*       │  /auth/v1/*   │
│    ↓     │   /channels     │       ↓         │      ↓        │
│   API    │      ↓          │  OpenClaw Node  │   GoTrue      │
│(memdog) │ Webhook Gateway │(webhook-gateway)│  (supabase)   │
└──────────┴────────┬────────┴─────────────────┴───────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Webhook Pipeline   │
         │  NATS → 40 Agents   │
         │  Ollama (4b→27b)    │
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │     Supabase        │
         │  Postgres+pgvector  │
         │  PostgREST · Kong   │
         └─────────────────────┘
```

### GKE Namespaces

| Namespace | Components |
|-----------|-----------|
| `memdog` | API, API PVC |
| `webhook-pipeline` | NATS, webhook-receiver, webhook-agent, webhook-pull-worker, ollama, ollama-chat |
| `webhook-gateway` | Webhook Gateway, OpenClaw Node, `open-jaws` Gateway |
| `supabase` | PostgreSQL, PostgREST, GoTrue, Kong, Realtime, Meta, Studio |

---

## Common Operations

### Restart all deployments

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh restart-gke -p memdog-dev -e dev
```

### Check deployment status

```bash
./scripts/manual-deploy.sh status -p memdog-dev -e dev
```

### View logs

```bash
# API
kubectl logs -n memdog deployment/api -f --tail=50

# Webhook agent
kubectl logs -n webhook-pipeline deployment/webhook-agent -f --tail=50

# Webhook gateway
kubectl logs -n webhook-gateway deployment/webhook-gateway -f --tail=50

# GoTrue (auth)
kubectl logs -n supabase deployment/supabase-auth -f --tail=50
```

### Redeploy a single component

```bash
# Just the API
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-api-gke -p memdog-dev -e dev

# Just the UI
NEXT_PUBLIC_SUPABASE_ANON_KEY="<key>" SUPABASE_AUTH_URL="http://<GATEWAY_IP>" \
  ./scripts/manual-deploy.sh deploy-ui -p memdog-dev -e dev
```

### Access Supabase Studio

```bash
kubectl port-forward -n supabase svc/supabase-studio 3001:3000
# Open http://localhost:3001
```

### Seed demo data

```bash
./scripts/seed-demo-user.sh -p memdog-dev -e dev
```

---

## Troubleshooting

### Pod stuck in CrashLoopBackOff

```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
```

### Gateway returns 404

Check HTTPRoutes are attached:

```bash
kubectl get httproute -A
kubectl describe gateway open-jaws -n webhook-gateway
```

### Auth not working

1. Verify GoTrue is healthy: `curl http://<GATEWAY_IP>/auth/v1/health`
2. Check the anon key is baked into the UI: look for `supabaseConfigured` in the browser console
3. Verify the `/auth/v1/*` rewrite is active: `SUPABASE_AUTH_URL` must be set at UI build time

### Ollama models not loading

Models are pulled on first request. Check logs:

```bash
kubectl logs -n webhook-pipeline deployment/ollama -f
kubectl logs -n webhook-pipeline deployment/ollama-chat -f
```

### Docker buildx issues on Mac

If cross-platform builds fail:

```bash
docker buildx create --use --name memdog-builder
docker buildx inspect --bootstrap
```
