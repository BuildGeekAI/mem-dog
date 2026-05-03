# Todoist

Connect Todoist to mem-dog to sync projects, tasks, and productivity data.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Todoist

1. In the UI, go to **Settings > Apps**
2. Find **Todoist** under the "Productivity" category
3. Click **Connect**
4. Authorize mem-dog via Todoist's OAuth consent screen
5. The Todoist card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Todoist account.

Query Todoist via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/todoist/rest/v2/tasks \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Projects and sections
- Tasks with labels and priorities
- Comments and attachments
- Completed task history

## Ingest into mem-dog

Pull data from Todoist and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Todoist data>",
    "source": "todoist",
    "meta_data": {}
  }'
```
