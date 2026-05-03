# Contentful

Connect Contentful to mem-dog to sync content entries, assets, and space data.

**Category:** Commerce & Content
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Contentful

1. In the UI, go to **Settings > Apps**
2. Find **Contentful** under the "Commerce & Content" category
3. Click **Connect**
4. Authorize mem-dog via Contentful's OAuth consent screen
5. The Contentful card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Contentful space.

Query Contentful via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/contentful/spaces/<space-id>/environments/master/entries \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, go to **Settings > Webhooks** in Contentful and add your `inbound_url`.

## What Gets Ingested

- Content entries and fields
- Assets (images, files)
- Content types and models
- Localized content

## Ingest into mem-dog

Pull data from Contentful and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Contentful data>",
    "source": "contentful",
    "meta_data": {}
  }'
```
