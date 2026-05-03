# ClickUp

Connect ClickUp to memdog to sync spaces, tasks, and project data.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect ClickUp

1. In the UI, go to **Settings > Apps**
2. Find **ClickUp** under the "Productivity" category
3. Click **Connect**
4. Authorize memdog via ClickUp's OAuth consent screen
5. The ClickUp card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your ClickUp workspace.

Query ClickUp via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/clickup/api/v2/team \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, create via:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/clickup/api/v2/team/<team-id>/webhook \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"endpoint": "https://<webhook-gateway>/webhooks/whk_<ulid>", "events": ["taskCreated", "taskUpdated"]}'
```

## What Gets Ingested

- Tasks and subtasks
- Spaces, folders, and lists
- Comments and attachments
- Time tracking entries

## Ingest into memdog

Pull data from ClickUp and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<ClickUp data>",
    "source": "clickup",
    "meta_data": {}
  }'
```
