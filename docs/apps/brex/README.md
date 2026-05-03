# Brex

Connect Brex to memdog to sync expense data, transactions, and card activity.

**Category:** Finance
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Brex

1. In the UI, go to **Settings > Apps**
2. Find **Brex** under the "Finance" category
3. Click **Connect**
4. Enter your Brex API Key when prompted
5. The Brex card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your Brex API token during setup.

Query Brex via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/brex/v2/transactions/card/primary \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Card transactions
- Expense reports
- Budget data
- Cash account activity

## Ingest into memdog

Pull data from Brex and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Brex data>",
    "source": "brex",
    "meta_data": {}
  }'
```
