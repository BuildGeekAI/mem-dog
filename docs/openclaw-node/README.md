# OpenClaw Node (DigiMe)

OpenClaw Node runs **DigiMe**, a conversational AI memory assistant that communicates with the memdog RAG system. Unlike the automated webhook pipeline, DigiMe is a user-facing agent that helps users manage their digital memory across 25+ messaging channels (WhatsApp, Signal, Telegram, Discord, Slack, and more).

## Architecture

```
User (WhatsApp, Signal, etc.)
        │
        ▼
  OpenClaw Gateway (port 18789)
        │
        ▼
     DigiMe Agent (Gemini LLM)
        │
        ├──→ memdog-bridge    → Webhook Gateway → Pipeline (records ALL messages)
        ├──→ memdog-ingest    → API /api/v1/data (stores notes/memories)
        ├──→ memdog-query     → API /api/v1/memories, /api/v1/data (retrieves data)
        └──→ memdog-semantic-search → API /api/v1/ai/query/semantic (vector search)
```

OpenClaw Node lives in the `webhook-gateway` k8s namespace alongside the webhook gateway. Traffic routes through the Gateway at `/oc/*`.

## Skills (memdog Integration)

DigiMe uses four skills to communicate with memdog:

### memdog-bridge
Forwards **every** incoming message to the webhook pipeline for recording, classification, and storage.

```
POST ${WEBHOOK_BRIDGE_URL}  (default: webhook-gateway:8080/webhooks/openclaw)

{
  "channel": "whatsapp",
  "text": "Remember my flight is at 3pm tomorrow",
  "sender": "+19251234567",
  "chatId": "+19251234567@s.whatsapp.net",
  "messageId": "msg_abc123",
  "attachments": [],
  "userId": "user_01ABC"
}
```

### memdog-ingest
Stores new data, notes, or memories explicitly.

```
POST ${MEM_DOG_API_URL}/api/v1/data
Headers: x-api-key: ${MEM_DOG_API_KEY}

{
  "content": "User's flight is at 3pm on 2026-03-20",
  "metadata": {
    "source": "digime",
    "channel": "whatsapp",
    "type": "fact",
    "tags": ["travel"]
  }
}
```

### memdog-query
Retrieves stored memories and data items.

```
GET ${MEM_DOG_API_URL}/api/v1/memories?limit=20
GET ${MEM_DOG_API_URL}/api/v1/data?limit=20&tags=session,whatsapp
Headers: x-api-key: ${MEM_DOG_API_KEY}
```

### memdog-semantic-search
Vector similarity search using natural language.

```
POST ${MEM_DOG_API_URL}/api/v1/ai/query/semantic
Headers: x-api-key: ${MEM_DOG_API_KEY}

{
  "query": "what time is the flight?",
  "max_results": 10,
  "synthesise": false
}
```

## Message Flow

For every incoming message, DigiMe follows this workflow:

1. **Record** — Forward the message to `memdog-bridge` (non-negotiable, every message)
2. **Session** — If first message from this sender, create a session memory via `memdog-ingest` (format: `{channel}_{sender}_{timestamp}`)
3. **Process** — Handle the user's request
4. **Recall** — If the user asks about past info, query via `memdog-query` or `memdog-semantic-search`

## Supported Channels

DigiMe receives messages from any OpenClaw-supported channel:

| Channel | Sender Format | Chat ID Format |
|---------|--------------|----------------|
| WhatsApp | Phone number | phone@s.whatsapp.net or group JID |
| Signal | Signal number/UUID | Conversation ID |
| Telegram | Username/ID | Chat ID |
| Discord | username#discriminator | Channel ID |
| Slack | User ID | Channel ID |
| Matrix | @user:server | !room:server |
| IRC | Nick | #channel |
| Email | Email address | Thread ID |
| Teams | Native ID | Native ID |
| LINE | Native ID | Native ID |
| Google Chat | Native ID | Native ID |

Plus 15+ more via the OpenClaw runtime.

## Deployment (GKE)

### Prerequisites

- GKE cluster `open-jaw` running in `us-central1-a`
- memdog API deployed in `memdog` namespace
- Webhook gateway deployed in `webhook-gateway` namespace
- PVC `openclaw-home` created in `webhook-gateway` namespace

### Required Secrets

```bash
# Generate a gateway token
OPENCLAW_GATEWAY_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Get your memdog API key (per-user key with md_ prefix)
MEM_DOG_API_KEY="md_your_api_key_here"

# Google Gemini API key
GEMINI_API_KEY="your_gemini_key"
```

### Deploy

```bash
GEMINI_API_KEY="$GEMINI_API_KEY" \
OPENCLAW_GATEWAY_TOKEN="$OPENCLAW_GATEWAY_TOKEN" \
MEM_DOG_API_KEY="$MEM_DOG_API_KEY" \
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-openclaw-node-gke -p memdog-dev -e dev
```

The deploy script:
1. Builds the Docker image (`openclaw-node/Dockerfile`) for `linux/amd64`
2. Pushes to Artifact Registry (`us-central1-docker.pkg.dev/memdog-dev/memdog/openclaw-node:dev-latest`)
3. Creates k8s secret `openclaw-node-secrets` in `webhook-gateway` namespace
4. Creates ConfigMap `openclaw-node-config`
5. Applies deployment, service, and HTTPRoute manifests
6. Waits for rollout (120s timeout)

### Verify

```bash
# Check pod status
kubectl get pods -n webhook-gateway -l app=openclaw-node

# Check logs
kubectl logs -n webhook-gateway -l app=openclaw-node -f

# Test health
kubectl exec -n webhook-gateway deploy/openclaw-node -- curl -s localhost:18789/healthz
```

### Kubernetes Resources

| Resource | Details |
|----------|---------|
| **Namespace** | `webhook-gateway` (shared with webhook-gateway) |
| **Deployment** | `openclaw-node` — init container copies skills from ConfigMaps to PVC |
| **Service** | ClusterIP on port 18789 |
| **HTTPRoute** | `/oc/*` → openclaw-node:18789 (prefix stripped) |
| **BackendPolicy** | 86400s timeout (24h) for WebSocket persistence |
| **HealthCheck** | `/healthz` every 15s |
| **PVC** | `openclaw-home` for persistent state |
| **Secret** | `openclaw-node-secrets` (GEMINI_API_KEY, OPENCLAW_GATEWAY_TOKEN, MEM_DOG_API_KEY) |
| **ConfigMaps** | `openclaw-node-config` (env vars), `openclaw-node-config-file` (openclaw.json), `openclaw-node-skills` (skill definitions + IDENTITY.md + SOUL.md) |

### Resource Limits

```
Requests: 50m CPU, 512Mi memory
Limits:   2 CPU,   4Gi memory
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google Generative AI API key |
| `OPENCLAW_GATEWAY_TOKEN` | Yes | — | WebSocket auth token for control UI |
| `MEM_DOG_API_KEY` | Yes | — | memdog API key for all skill calls |
| `GEMINI_MODEL` | No | `gemini-3.1-pro-preview` | Gemini model to use |
| `MEM_DOG_API_URL` | No | `http://api.memdog.svc.cluster.local:8080` | memdog API base URL |
| `WEBHOOK_BRIDGE_URL` | No | `http://webhook-gateway.webhook-gateway.svc.cluster.local:8080/webhooks/openclaw` | Bridge endpoint |
| `LOG_LEVEL` | No | `info` | Log level |
| `OPENCLAW_GATEWAY_PORT` | No | `18789` | Gateway listen port |
| `OPENCLAW_GATEWAY_BIND` | No | `lan` | Bind mode |

### Agent Configuration (`openclaw.json.tmpl`)

The OpenClaw config template defines:
- **Identity**: Name "DigiMe", emoji 🧠, theme "friendly digital memory assistant"
- **Model**: `google/${GEMINI_MODEL}` via Google Generative AI API
- **Skills**: Bundled `healthcheck` + custom memdog skills from `/data/.openclaw/skills/`
- **Auth**: Token-based gateway authentication

## Docker Build

The `openclaw-node/Dockerfile` builds on `coollabsio/openclaw:latest`:

1. Installs nginx (reverse proxy: port 8080 → 18789)
2. Copies skills to `/data/.openclaw/skills/`
3. Copies `entrypoint.sh` and `openclaw.json.tmpl`
4. Exposes port 8080

The entrypoint script:
1. Creates state/workspace directories
2. Runs OpenClaw `configure.js` initialization
3. Patches config for wildcard WebSocket origins
4. Starts nginx + OpenClaw gateway

## DigiMe Identity

DigiMe operates under strict rules defined in `SOUL.md`:

1. **Always record** — Every message forwarded to memdog-bridge before responding
2. **No local files** — All memory operations go through the memdog API, never workspace files
3. **Session tracking** — Creates session memories on first contact from each sender
4. **Identity** — Always identifies as DigiMe, never as AI/OpenClaw/Gemini
5. **Proactive recall** — Uses semantic search when users ask about past information

## Key Files

| Path | Purpose |
|------|---------|
| `openclaw-node/Dockerfile` | Container build |
| `openclaw-node/entrypoint.sh` | Startup: config + nginx + gateway |
| `openclaw-node/openclaw.json.tmpl` | Runtime config template |
| `openclaw-node/skills/memdog-bridge/` | Forward all messages to pipeline |
| `openclaw-node/skills/memdog-ingest/` | Store data/memories |
| `openclaw-node/skills/memdog-query/` | Retrieve memories/data |
| `openclaw-node/skills/memdog-semantic-search/` | Vector search |
| `k8s/openclaw-node/deployment.yaml` | Pod + init container |
| `k8s/openclaw-node/skills-configmap.yaml` | Skill docs + SOUL.md + IDENTITY.md |
| `k8s/openclaw-node/configmap.yaml` | Environment config |
| `k8s/openclaw-node/secret.yaml` | API keys and tokens |
| `k8s/openclaw-node/httproute.yaml` | Gateway routing `/oc/*` |
| `webhook-gateway/app/channels/openclaw_bridge.py` | Webhook adapter for OpenClaw messages |
