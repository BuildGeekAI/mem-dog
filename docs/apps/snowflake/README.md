# Snowflake

Connect Snowflake to mem-dog to query data warehouse tables and views.

**Category:** Data & AI
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Snowflake

1. In the UI, go to **Settings > Apps**
2. Find **Snowflake** under the "Data & AI" category
3. Click **Connect**
4. Enter your Snowflake API Key when prompted
5. The Snowflake card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your Snowflake account credentials during setup.

Query Snowflake via the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/snowflake/api/v2/statements \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"statement": "SELECT * FROM my_table LIMIT 10", "database": "MY_DB", "schema": "PUBLIC"}'
```

## What Gets Ingested

- Query results
- Table and schema metadata
- Usage and cost data

## Ingest into mem-dog

Pull data from Snowflake and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Snowflake data>",
    "source": "snowflake",
    "meta_data": {}
  }'
```
