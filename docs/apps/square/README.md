# Square

Connect Square to memdog to sync payments, orders, and catalog data.

**Category:** Finance
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Square

1. In the UI, go to **Settings > Apps**
2. Find **Square** under the "Finance" category
3. Click **Connect**
4. Authorize memdog via Square's OAuth consent screen
5. The Square card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Square account.

Query Square via the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/square/v2/payments \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, configure in the Square Developer Dashboard under **Webhooks**.

## What Gets Ingested

- Payment transactions
- Orders and line items
- Customer profiles
- Inventory and catalog data

## Ingest into memdog

Pull data from Square and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Square data>",
    "source": "square",
    "meta_data": {}
  }'
```
