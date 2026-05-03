# Basecamp

Connect Basecamp to mem-dog to sync projects, to-dos, and team discussions.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Basecamp

1. In the UI, go to **Settings > Apps**
2. Find **Basecamp** under the "Productivity" category
3. Click **Connect**
4. Authorize mem-dog via Basecamp's OAuth consent screen
5. The Basecamp card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Basecamp account.

Query Basecamp via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/basecamp/<account-id>/projects.json \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Projects and to-do lists
- Messages and comments
- Documents and files
- Campfire chat messages
- Schedule entries

## Ingest into mem-dog

Pull data from Basecamp and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Basecamp data>",
    "source": "basecamp",
    "meta_data": {}
  }'
```
