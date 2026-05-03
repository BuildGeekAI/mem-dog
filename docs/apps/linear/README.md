# Linear

Connect Linear to memdog to sync issues, projects, and engineering workflows.

**Category:** Dev Tools
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Linear

1. In the UI, go to **Settings > Apps**
2. Find **Linear** under the "Dev Tools" category
3. Click **Connect**
4. Enter your Linear API Key when prompted
5. The Linear card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your Linear API key during setup.

Query Linear via GraphQL through the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/linear/graphql \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ issues(first: 10) { nodes { id title state { name } } } }"}'
```

For webhooks, configure in **Settings > API > Webhooks** in Linear.

## What Gets Ingested

- Issues and sub-issues
- Projects and cycles
- Comments and reactions
- Team and workflow states

## Ingest into memdog

Pull data from Linear and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Linear data>",
    "source": "linear",
    "meta_data": {}
  }'
```
