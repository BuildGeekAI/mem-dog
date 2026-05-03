# Notion

Connect Notion to mem-dog to sync pages, databases, and workspace content into your knowledge base.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Notion

1. In the UI, go to **Settings > Apps**
2. Find **Notion** under the "Productivity" category
3. Click **Connect**
4. Authorize mem-dog to access your Notion workspace
5. Select the pages/databases you want to share with mem-dog
6. The Notion card should now show **Active**

### 3. Sync Content

Notion is an outbound integration -- mem-dog pulls data from Notion's API rather than receiving webhooks. Use the integration proxy to query your Notion workspace:

```bash
# Search all pages
curl -X POST https://<your-api>/api/v1/integrations/proxy/notion/search \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"query": "meeting notes"}'

# Get a specific page
curl https://<your-api>/api/v1/integrations/proxy/notion/pages/<page-id> \
  -H "Authorization: Bearer <your-jwt>"

# Query a database
curl -X POST https://<your-api>/api/v1/integrations/proxy/notion/databases/<db-id>/query \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## What You Can Access

- Pages and sub-pages (full content blocks)
- Databases and their entries
- Comments on pages
- User and workspace metadata

## Tip: Periodic Sync

To keep Notion content up to date in mem-dog, set up a periodic job that queries Notion for recently modified pages and ingests them via the mem-dog data API:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<page content>",
    "source": "notion",
    "meta_data": {"notion_page_id": "<page-id>"}
  }'
```
