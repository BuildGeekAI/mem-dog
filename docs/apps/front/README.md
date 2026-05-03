# Front

Connect Front to mem-dog to sync conversations, contacts, and team inbox data.

**Category:** Customer Support
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Front

1. In the UI, go to **Settings > Apps**
2. Find **Front** under the "Customer Support" category
3. Click **Connect**
4. Authorize mem-dog via Front's OAuth consent screen
5. The Front card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Front account.

Query Front via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/front/conversations \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, configure in **Settings > Developers > Webhooks** in Front.

## What Gets Ingested

- Conversations and messages
- Contact data
- Tags and assignments
- Team analytics

## Ingest into mem-dog

Pull data from Front and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Front data>",
    "source": "front",
    "meta_data": {}
  }'
```
