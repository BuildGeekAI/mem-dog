# Google Docs

Connect Google Docs to mem-dog to sync document content into your knowledge base.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Google Docs

1. In the UI, go to **Settings > Apps**
2. Find **Google Docs** under the "Productivity" category
3. Click **Connect**
4. Authorize mem-dog via Google Docs's OAuth consent screen
5. The Google Docs card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow via Google. Access is through the Google Docs and Drive APIs.

Query docs via the proxy:

```bash
# Get document content
curl https://<your-api>/api/v1/integrations/proxy/google-docs/v1/documents/<doc-id> \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Document text content
- Comments and suggestions
- Revision history
- Shared document metadata

## Ingest into mem-dog

Pull data from Google Docs and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Google Docs data>",
    "source": "google-docs",
    "meta_data": {}
  }'
```
