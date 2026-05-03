# Monday.com

Connect Monday.com to memdog to sync boards, items, and workflow data.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Monday.com

1. In the UI, go to **Settings > Apps**
2. Find **Monday.com** under the "Productivity" category
3. Click **Connect**
4. Authorize memdog via Monday.com's OAuth consent screen
5. The Monday.com card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Monday.com account.

Monday.com uses GraphQL. Query via the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/monday/v2 \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ boards (limit:5) { id name items_page { items { id name } } } }"}'
```

## What Gets Ingested

- Boards and groups
- Items with column values
- Updates and replies
- Activity logs

## Ingest into memdog

Pull data from Monday.com and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Monday.com data>",
    "source": "monday",
    "meta_data": {}
  }'
```
