# WooCommerce

Connect WooCommerce to memdog to sync orders, products, and store data.

**Category:** Commerce & Content
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect WooCommerce

1. In the UI, go to **Settings > Apps**
2. Find **WooCommerce** under the "Commerce & Content" category
3. Click **Connect**
4. Authorize memdog via WooCommerce's OAuth consent screen
5. The WooCommerce card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your WordPress/WooCommerce site.

Query WooCommerce via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/woocommerce/wp-json/wc/v3/orders \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, go to **WooCommerce > Settings > Advanced > Webhooks** and add your `inbound_url`.

## What Gets Ingested

- Orders and customers
- Product catalog
- Coupons and tax data
- Shipping and payment methods

## Ingest into memdog

Pull data from WooCommerce and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<WooCommerce data>",
    "source": "woocommerce",
    "meta_data": {}
  }'
```
