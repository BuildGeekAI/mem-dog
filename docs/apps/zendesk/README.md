# Zendesk

Connect Zendesk to memdog to ingest support tickets, conversations, and knowledge base content.

**Category:** Customer Support
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Zendesk

1. In the UI, go to **Settings > Apps**
2. Find **Zendesk** under the "Customer Support" category
3. Click **Connect**
4. Authorize memdog via Zendesk's OAuth consent screen
5. The Zendesk card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "zendesk", "name": "My Zendesk Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Zendesk Events

OAuth2 flow connects to your Zendesk subdomain.

1. In Zendesk Admin, go to **Apps and integrations > Webhooks**
2. Create a webhook pointing to your `inbound_url`
3. Create a trigger that fires the webhook on ticket events

### 5. Data Flow

```
Zendesk event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Tickets and comments
- Customer profiles and organizations
- Knowledge base articles
- Satisfaction ratings

## Ingest into memdog

Data from Zendesk flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
