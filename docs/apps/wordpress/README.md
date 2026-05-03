# WordPress

Connect WordPress to mem-dog to sync posts, pages, and content data.

**Category:** Commerce & Content
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect WordPress

1. In the UI, go to **Settings > Apps**
2. Find **WordPress** under the "Commerce & Content" category
3. Click **Connect**
4. Authorize mem-dog via WordPress's OAuth consent screen
5. The WordPress card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your WordPress site (requires Jetpack or Application Passwords).

Query WordPress via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/wordpress/wp-json/wp/v2/posts \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Posts and pages
- Comments and revisions
- Media library items
- Categories and tags

## Ingest into mem-dog

Pull data from WordPress and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<WordPress data>",
    "source": "wordpress",
    "meta_data": {}
  }'
```
