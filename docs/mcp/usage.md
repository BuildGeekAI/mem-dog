# MCP Server Usage

## Connecting from Claude Desktop

1. Get your API key from the memdog UI (Settings > API Keys)
2. Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "memdog": {
      "url": "http://<gateway-ip>/mcp/sse",
      "headers": {
        "x-api-key": "md_your_api_key_here"
      }
    }
  }
}
```

3. Restart Claude Desktop

For local development, use `http://localhost:8091/mcp/sse` (docker compose) or `http://localhost:8090/mcp/sse` (manual).

## Connecting from Cursor

1. Open Cursor Settings > MCP
2. Add a new MCP server with:
   - **URL**: `http://<gateway-ip>/mcp/sse`
   - **Headers**: `x-api-key: md_your_api_key_here`

## Connecting from MCP Inspector

```bash
npx @modelcontextprotocol/inspector
# Enter URL: http://localhost:8091/mcp/sse
# Add header: x-api-key: md_your_api_key_here
```

## Authentication

All requests require an API key. Pass it via:
- **Header** (preferred): `x-api-key: md_...`
- **Query parameter**: `?api_key=md_...`

The API key scopes all tool calls to the authenticated user.

## Available Tools

### search

Semantic/hybrid search across stored data.

```
query: "meeting notes about Q1 goals"
max_results: 5
search_mode: "hybrid"  # vector, fts, hybrid, graph, full
```

### add

Store text content with optional metadata.

```
content: "The quarterly review concluded that..."
name: "Q1 Review Notes"
tags: "meeting,quarterly,review"
memory_type: "conversation"
```

### get

Retrieve a data item by ID.

```
data_id: "data_01HXYZ..."
```

### delete

Delete a data item.

```
data_id: "data_01HXYZ..."
```

### entities

Search knowledge graph entities.

```
query: "Acme"
entity_type: "organization"
limit: 10
```

### chat

RAG conversational query with citations.

```
message: "What were the key decisions from last week?"
search_mode: "hybrid"
max_results: 5
```

Returns an AI-generated answer with `[1][2]` citation markers linking to source documents.

### memories

List or create memory containers.

```
action: "list"       # or "create"
memory_type: "conversation"
name: "Sprint 42 Notes"
limit: 20
```

Memory types: `timeline`, `session`, `conversation`, `user`, `organizational`, `factual`, `episodic`, `semantic`, `custom`, `tracing`.

### list_data

Browse stored data items with metadata.

```
limit: 20
offset: 0
```
