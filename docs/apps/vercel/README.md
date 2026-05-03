# Vercel

Connect Vercel to memdog to sync deployment data and project configuration.

**Category:** Dev Tools
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Vercel

1. In the UI, go to **Settings > Apps**
2. Find **Vercel** under the "Dev Tools" category
3. Click **Connect**
4. Authorize memdog via Vercel's OAuth consent screen
5. The Vercel card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Vercel account.

Query Vercel via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/vercel/v6/deployments \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, configure in Vercel project **Settings > Webhooks**.

## What Gets Ingested

- Deployment events and status
- Project configuration
- Domain and environment settings
- Build logs

## Ingest into memdog

Pull data from Vercel and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Vercel data>",
    "source": "vercel",
    "meta_data": {}
  }'
```
