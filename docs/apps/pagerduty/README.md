# PagerDuty

Connect PagerDuty to mem-dog to ingest incidents, alerts, and on-call schedules.

**Category:** Dev Tools
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect PagerDuty

1. In the UI, go to **Settings > Apps**
2. Find **PagerDuty** under the "Dev Tools" category
3. Click **Connect**
4. Authorize mem-dog via PagerDuty's OAuth consent screen
5. The PagerDuty card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "pagerduty", "name": "My PagerDuty Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure PagerDuty Events

OAuth2 flow connects to your PagerDuty account.

1. In PagerDuty, go to **Integrations > Generic Webhooks (v3)**
2. Create a webhook subscription
3. Set the **Delivery URL** to your `inbound_url`
4. Select event types: `incident.triggered`, `incident.resolved`, `incident.acknowledged`

### 5. Data Flow

```
PagerDuty event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Incident creation and resolution
- Alert triggers and acknowledgements
- On-call schedule changes
- Service and escalation data

## Ingest into mem-dog

Data from PagerDuty flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
