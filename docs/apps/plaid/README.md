# Plaid

Connect Plaid to memdog to sync bank account data, transactions, and balances.

**Category:** Finance
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Plaid

1. In the UI, go to **Settings > Apps**
2. Find **Plaid** under the "Finance" category
3. Click **Connect**
4. Authorize memdog via Plaid's OAuth consent screen
5. The Plaid card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow via Plaid Link.

Plaid uses webhooks for async updates:
1. Set the webhook URL when creating a Plaid Link token
2. Point to your `inbound_url`
3. Plaid will POST transaction and account updates

## What Gets Ingested

- Account balances
- Transaction history
- Identity verification data
- Investment holdings

## Ingest into memdog

Pull data from Plaid and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Plaid data>",
    "source": "plaid",
    "meta_data": {}
  }'
```
