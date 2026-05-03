# Netlify

Connect Netlify to memdog to sync site data, deploys, and build information.

**Category:** Dev Tools
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Netlify

1. In the UI, go to **Settings > Apps**
2. Find **Netlify** under the "Dev Tools" category
3. Click **Connect**
4. Authorize memdog via Netlify's OAuth consent screen
5. The Netlify card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Netlify account.

Query Netlify via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/netlify/api/v1/sites \
  -H "Authorization: Bearer <your-jwt>"
```

For deploy notifications, add your `inbound_url` under **Site Settings > Build & Deploy > Deploy Notifications**.

## What Gets Ingested

- Deploy events and build logs
- Site configuration
- Form submissions
- Split test data

## Ingest into memdog

Pull data from Netlify and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Netlify data>",
    "source": "netlify",
    "meta_data": {}
  }'
```
