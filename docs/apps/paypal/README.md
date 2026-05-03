# PayPal

Connect PayPal to memdog to sync payment data, transactions, and disputes.

**Category:** Finance
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect PayPal

1. In the UI, go to **Settings > Apps**
2. Find **PayPal** under the "Finance" category
3. Click **Connect**
4. Authorize memdog via PayPal's OAuth consent screen
5. The PayPal card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your PayPal business account.

For webhooks:
1. In the PayPal Developer Dashboard, go to **My Apps & Credentials**
2. Select your app and go to **Webhooks**
3. Add your `inbound_url` and select event types

## What Gets Ingested

- Payment captures and authorizations
- Transaction history
- Dispute and refund events
- Subscription billing events

## Ingest into memdog

Pull data from PayPal and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<PayPal data>",
    "source": "paypal",
    "meta_data": {}
  }'
```
