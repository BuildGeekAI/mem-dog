# LinkedIn

Connect LinkedIn to memdog to access profile data, posts, and company pages.

**Category:** Social Media
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect LinkedIn

1. In the UI, go to **Settings > Apps**
2. Find **LinkedIn** under the "Social Media" category
3. Click **Connect**
4. Authorize memdog via LinkedIn's OAuth consent screen
5. The LinkedIn card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

Requires a LinkedIn Developer app with appropriate API products.

Query LinkedIn data via the integration proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/linkedin/v2/me \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Profile and company page data
- Posts and articles
- Comments and reactions

## Ingest into memdog

Pull data from LinkedIn and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<LinkedIn data>",
    "source": "linkedin",
    "meta_data": {}
  }'
```
