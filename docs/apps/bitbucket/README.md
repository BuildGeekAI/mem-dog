# Bitbucket

Connect Bitbucket to memdog to sync repositories, pull requests, and pipelines.

**Category:** Dev Tools
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Bitbucket

1. In the UI, go to **Settings > Apps**
2. Find **Bitbucket** under the "Dev Tools" category
3. Click **Connect**
4. Authorize memdog via Bitbucket's OAuth consent screen
5. The Bitbucket card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Atlassian/Bitbucket account.

Query Bitbucket via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/bitbucket/2.0/repositories/<workspace> \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, go to **Repository Settings > Webhooks** and set the URL to your `inbound_url`.

## What Gets Ingested

- Pull requests and reviews
- Repository push events
- Pipeline build results
- Issue tracker data

## Ingest into memdog

Pull data from Bitbucket and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Bitbucket data>",
    "source": "bitbucket",
    "meta_data": {}
  }'
```
