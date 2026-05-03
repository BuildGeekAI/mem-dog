# Stripe

Connect Stripe to memdog to ingest payment events, invoices, and customer data.

**Category:** Finance
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Stripe

1. In the UI, go to **Settings > Apps**
2. Find **Stripe** under the "Finance" category
3. Click **Connect**
4. Authorize memdog via Stripe's OAuth consent screen
5. The Stripe card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "stripe", "name": "My Stripe Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Stripe Events

OAuth2 flow (Stripe Connect) links your Stripe account.

1. In the Stripe Dashboard, go to **Developers > Webhooks**
2. Click **Add endpoint**
3. Set the **Endpoint URL** to your `inbound_url`
4. Select events: `payment_intent.succeeded`, `invoice.paid`, `customer.created`, etc.

### 5. Data Flow

```
Stripe event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Payment intents and charges
- Invoice and subscription events
- Customer data and metadata
- Dispute and refund notifications

## Ingest into memdog

Data from Stripe flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
