# Sentry

Connect Sentry to mem-dog to ingest error events, alerts, and issue data.

**Category:** Dev Tools
**Auth:** API Key
**Direction:** Inbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Sentry

1. In the UI, go to **Settings > Apps**
2. Find **Sentry** under the "Dev Tools" category
3. Click **Connect**
4. Enter your Sentry API Key when prompted
5. The Sentry card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "sentry", "name": "My Sentry Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Sentry Events

Provide your Sentry auth token during setup.

1. In Sentry, go to **Settings > Developer Settings > Webhooks** (or Internal Integration)
2. Set the **Webhook URL** to your `inbound_url`
3. Subscribe to: `issue`, `error`, `event_alert`

### 5. Data Flow

```
Sentry event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Error events and stack traces
- Issue alerts and notifications
- Release and deploy data
- Performance transaction data

## Ingest into mem-dog

Data from Sentry flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
