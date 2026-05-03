# Box

Connect Box to mem-dog to sync files, folders, and collaboration data.

**Category:** Cloud & Storage
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Box

1. In the UI, go to **Settings > Apps**
2. Find **Box** under the "Cloud & Storage" category
3. Click **Connect**
4. Authorize mem-dog via Box's OAuth consent screen
5. The Box card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Box account.

Query Box via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/box/2.0/folders/0/items \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, create via:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/box/2.0/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"target": {"id": "<folder-id>", "type": "folder"}, "address": "https://<webhook-gateway>/webhooks/whk_<ulid>", "triggers": ["FILE.UPLOADED"]}'
```

## What Gets Ingested

- Files and folder hierarchy
- Comments and tasks on files
- Shared links and collaborations
- Metadata templates

## Ingest into mem-dog

Pull data from Box and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Box data>",
    "source": "box",
    "meta_data": {}
  }'
```
