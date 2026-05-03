# WhatsApp Business

Connect WhatsApp Business to mem-dog to ingest customer conversations and media.

**Category:** Messaging
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect WhatsApp Business

1. In the UI, go to **Settings > Apps**
2. Find **WhatsApp Business** under the "Messaging" category
3. Click **Connect**
4. Authorize mem-dog via WhatsApp Business's OAuth consent screen
5. The WhatsApp Business card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "whatsapp", "name": "My WhatsApp Business Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure WhatsApp Business Events

Requires a Meta Business account with WhatsApp Business API access.

1. Go to [developers.facebook.com](https://developers.facebook.com) and set up a WhatsApp Business app
2. Navigate to **WhatsApp > Configuration**
3. Set the **Callback URL** to your `inbound_url`
4. Set a **Verify token** and subscribe to `messages` events

### 5. Data Flow

```
WhatsApp Business event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Inbound and outbound messages
- Media (images, video, audio, documents)
- Message status updates (sent, delivered, read)
- Contact and location messages

## Ingest into mem-dog

Data from WhatsApp Business flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
