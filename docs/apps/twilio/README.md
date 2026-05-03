# Twilio

Connect Twilio to memdog to ingest SMS, MMS, and voice call data.

**Category:** Messaging
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Twilio

1. In the UI, go to **Settings > Apps**
2. Find **Twilio** under the "Messaging" category
3. Click **Connect**
4. Authorize memdog via Twilio's OAuth consent screen
5. The Twilio card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "twilio", "name": "My Twilio Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Twilio Events

Requires a Twilio account with an active phone number.

1. Go to [console.twilio.com](https://console.twilio.com)
2. Navigate to **Phone Numbers > Manage > Active Numbers**
3. Select your number and set the **Webhook URL** for messaging to your `inbound_url`
4. Set HTTP method to POST

### 5. Data Flow

```
Twilio event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- SMS and MMS messages
- Voice call metadata and recordings
- WhatsApp messages via Twilio
- Delivery status callbacks

## Ingest into memdog

Data from Twilio flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
