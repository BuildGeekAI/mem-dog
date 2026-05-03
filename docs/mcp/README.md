# MCP Server

The mem-dog MCP (Model Context Protocol) server exposes 8 tools over SSE transport, enabling Claude Desktop, Cursor, and other MCP-compatible agents to interact with the mem-dog API.

## Quick Start

### Claude Desktop

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mem-dog": {
      "url": "http://<gateway-ip>/mcp/sse",
      "headers": { "x-api-key": "md_your_key" }
    }
  }
}
```

### Local Development

```bash
docker compose up
# MCP endpoint: http://localhost:8091/mcp/sse
```

### GKE Deployment

```bash
GKE_CLUSTER=open-jaw GKE_ZONE=us-central1-a \
  ./scripts/manual-deploy.sh deploy-mcp-server-gke -p memdog-dev -e dev
```

## Tools

| Tool | Description |
|------|-------------|
| `search` | Semantic/hybrid search across stored data |
| `add` | Store text content with tags/memory association |
| `get` | Retrieve data item by ID |
| `delete` | Delete data item |
| `entities` | Search knowledge graph entities |
| `chat` | RAG conversational query with citations |
| `memories` | List or create memories |
| `list_data` | List stored data items |

## Architecture

```mermaid
graph TD
    subgraph Clients
        CD[Claude Desktop]
        CU[Cursor]
        MI[MCP Inspector]
    end

    subgraph GKE [GKE Cluster · mem-dog namespace]
        GW[Gateway<br/>open-jaws L7 LB]
        MCP[MCP Server<br/>FastMCP + FastAPI<br/>port 8080]
        API[mem-dog API<br/>FastAPI<br/>port 8080]
    end

    subgraph Storage
        PG[(Supabase Postgres<br/>pgvector + BM25)]
        NEO[(Neo4j<br/>Graphiti KG)]
        GCS[(GCS<br/>raw binary)]
    end

    CD -- "SSE<br/>x-api-key: md_..." --> GW
    CU -- "SSE<br/>x-api-key: md_..." --> GW
    MI -- "SSE" --> GW

    GW -- "/mcp/*" --> MCP
    MCP -- "httpx<br/>Bearer: md_..." --> API

    API --> PG
    API --> NEO
    API --> GCS

    style MCP fill:#7c3aed22,stroke:#8b5cf6,color:#c4b5fd
    style API fill:#10b98122,stroke:#10b981,color:#6ee7b7
    style GW fill:#06b6d422,stroke:#06b6d4,color:#67e8f9
    style PG fill:#06b6d422,stroke:#06b6d4,color:#67e8f9
    style NEO fill:#f59e0b22,stroke:#f59e0b,color:#fcd34d
    style GCS fill:#06b6d422,stroke:#06b6d4,color:#67e8f9
```

- **Namespace**: `mem-dog` (same as API for in-cluster HTTP)
- **Gateway path**: `/mcp/*` via `open-jaws` HTTPRoute
- **Auth**: `md_*` API keys forwarded to API on every tool call

## Docs

- [Setup & Deployment](setup.md)
- [Usage & Tool Reference](usage.md)
