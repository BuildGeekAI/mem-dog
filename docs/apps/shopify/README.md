# Shopify

Connect Shopify to memdog to ingest orders, products, and customer data.

**Category:** Commerce & Content
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Shopify

1. In the UI, go to **Settings > Apps**
2. Find **Shopify** under the "Commerce & Content" category
3. Click **Connect**
4. Authorize memdog via Shopify's OAuth consent screen
5. The Shopify card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "shopify", "name": "My Shopify Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Shopify Events

OAuth2 flow connects to your Shopify store.

1. In Shopify Admin, go to **Settings > Notifications > Webhooks**
2. Click **Create webhook**
3. Select the topic (e.g. `orders/create`)
4. Set the URL to your `inbound_url`
5. Select JSON format

### 5. Data Flow

```
Shopify event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Orders and line items
- Product catalog and inventory
- Customer profiles
- Checkout and cart events

## Ingest into memdog

Data from Shopify flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
