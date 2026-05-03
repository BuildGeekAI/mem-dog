# Airtable

Connect Airtable to memdog to sync bases, tables, and structured data.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Airtable

1. In the UI, go to **Settings > Apps**
2. Find **Airtable** under the "Productivity" category
3. Click **Connect**
4. Authorize memdog via Airtable's OAuth consent screen
5. The Airtable card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Airtable account.

Query Airtable via the proxy:

```bash
# List records
curl https://<your-api>/api/v1/integrations/proxy/airtable/v0/<base-id>/<table-name> \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/airtable/v0/bases/<base-id>/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"notificationUrl": "https://<webhook-gateway>/webhooks/whk_<ulid>", "specification": {"options": {"filters": {"dataTypes": ["tableData"]}}}}'
```

## What Gets Ingested

- Base and table schemas
- Records with field values
- Attachments and linked records
- View configurations

## Ingest into memdog

Pull data from Airtable and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Airtable data>",
    "source": "airtable",
    "meta_data": {}
  }'
```
