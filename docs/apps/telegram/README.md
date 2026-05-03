# Telegram

Connect Telegram to memdog to ingest bot messages, group chats, and media.

**Category:** Messaging
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Telegram

1. In the UI, go to **Settings > Apps**
2. Find **Telegram** under the "Messaging" category
3. Click **Connect**
4. Authorize memdog via Telegram's OAuth consent screen
5. The Telegram card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "telegram", "name": "My Telegram Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Telegram Events

Set up a Telegram Bot via @BotFather, then configure the webhook URL to point to your memdog endpoint.

1. Message @BotFather on Telegram and create a new bot
2. Copy the bot token
3. Set the webhook URL:

```bash
curl -X POST https://api.telegram.org/bot<token>/setWebhook \
  -d 'url=https://<webhook-gateway>/webhooks/whk_<ulid>'
```

### 5. Data Flow

```
Telegram event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Bot messages and group chats
- Media files (photos, videos, documents)
- Inline queries and callback data
- Channel posts

## Ingest into memdog

Data from Telegram flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
