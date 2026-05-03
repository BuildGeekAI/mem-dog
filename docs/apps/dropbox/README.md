# Dropbox

Connect Dropbox to memdog to sync files and folders into your knowledge base.

**Category:** Cloud & Storage
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Dropbox

1. In the UI, go to **Settings > Apps**
2. Find **Dropbox** under the "Cloud & Storage" category
3. Click **Connect**
4. Authorize memdog via Dropbox's OAuth consent screen
5. The Dropbox card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Dropbox account.

Query Dropbox via the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/dropbox/2/files/list_folder \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"path": ""}'
```

## What Gets Ingested

- Files and folder structure
- Shared links and permissions
- File revision history
- Team activity

## Ingest into memdog

Pull data from Dropbox and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Dropbox data>",
    "source": "dropbox",
    "meta_data": {}
  }'
```
