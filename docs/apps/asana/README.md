# Asana

Connect Asana to mem-dog to sync projects, tasks, and team workflows.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Asana

1. In the UI, go to **Settings > Apps**
2. Find **Asana** under the "Productivity" category
3. Click **Connect**
4. Authorize mem-dog via Asana's OAuth consent screen
5. The Asana card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Asana workspace.

Query Asana via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/asana/api/1.0/tasks?project=<project-gid> \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, create via the API:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/asana/api/1.0/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"data": {"resource": "<project-gid>", "target": "https://<webhook-gateway>/webhooks/whk_<ulid>"}}'
```

## What Gets Ingested

- Tasks and subtasks
- Projects and sections
- Comments and attachments
- Custom fields and tags

## Ingest into mem-dog

Pull data from Asana and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Asana data>",
    "source": "asana",
    "meta_data": {}
  }'
```
