# MCP Server Setup

The MCP server exposes mem-dog data, search, and RAG tools over SSE (Server-Sent Events) transport, enabling Claude Desktop, Cursor, and other MCP-compatible agents to interact with the mem-dog API.

## Architecture

- **Standalone Python service** in `mcp-server/` using the official `mcp` SDK with SSE transport
- **Thin proxy** over the mem-dog API — reuses the `mem_dog_client` Python SDK
- **Per-user auth** via `md_*` API keys forwarded to the API on every tool call
- **GKE namespace**: `mem-dog` (same as API, for direct in-cluster HTTP)

## Local Development

### Docker Compose (recommended)

```bash
docker compose up
# MCP server available at http://localhost:8091/mcp/sse
```

### Manual

```bash
cd mcp-server
pip install -e ../client   # Install mem-dog client SDK
pip install -e ".[dev]"    # Install MCP server + dev deps
uvicorn app.main:app --reload --port 8090
# MCP server at http://localhost:8090/mcp/sse
```

### Health Checks

- `GET /health` — liveness probe
- `GET /ready` — readiness probe

## GKE Deployment

### Deploy

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-mcp-server-gke -p memdog-dev -e dev
```

### K8s Resources

| File | Purpose |
|------|---------|
| `k8s/mcp-server-deployment.yaml` | Deployment (100m/128Mi req, 500m/256Mi limit) |
| `k8s/mcp-server-service.yaml` | ClusterIP on port 8080 |
| `k8s/mcp-server-configmap.yaml` | `MEM_DOG_API_URL`, `LOG_LEVEL`, `PORT` |
| `k8s/mcp-server-httproute.yaml` | `/mcp/*` → mcp-server via `open-jaws` Gateway |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEM_DOG_API_URL` | `http://localhost:8080` | mem-dog API base URL |
| `PORT` | `8090` | Server listen port |
| `LOG_LEVEL` | `INFO` | Python log level |

In GKE, `MEM_DOG_API_URL` is set to `http://api.mem-dog.svc.cluster.local:8080` for in-cluster communication.

### External Access

After deployment, the MCP server is accessible via the gateway:

```
http://<gateway-ip>/mcp/sse
```

The gateway IP is the same one used for the webhook gateway (`34.36.80.165` in dev).
