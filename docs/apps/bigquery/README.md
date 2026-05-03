# BigQuery

Connect BigQuery to mem-dog to query datasets and sync analytics data.

**Category:** Data & AI
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect BigQuery

1. In the UI, go to **Settings > Apps**
2. Find **BigQuery** under the "Data & AI" category
3. Click **Connect**
4. Authorize mem-dog via BigQuery's OAuth consent screen
5. The BigQuery card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow via Google Cloud.

Query BigQuery via the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/bigquery/bigquery/v2/projects/<project>/queries \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM dataset.table LIMIT 10", "useLegacySql": false}'
```

## What Gets Ingested

- Query results
- Dataset and table schemas
- Job metadata

## Ingest into mem-dog

Pull data from BigQuery and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<BigQuery data>",
    "source": "bigquery",
    "meta_data": {}
  }'
```
