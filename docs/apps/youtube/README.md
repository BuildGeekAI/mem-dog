# YouTube

Connect YouTube to mem-dog to ingest video metadata, comments, and channel activity.

**Category:** Social Media
**Auth:** OAuth2
**Direction:** Inbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect YouTube

1. In the UI, go to **Settings > Apps**
2. Find **YouTube** under the "Social Media" category
3. Click **Connect**
4. Authorize mem-dog via YouTube's OAuth consent screen
5. The YouTube card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "youtube", "name": "My YouTube Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure YouTube Events

Uses YouTube Data API v3.

For real-time notifications, use YouTube's PubSubHubbub:

```bash
curl -X POST https://pubsubhubbub.appspot.com/subscribe \
  -d 'hub.callback=https://<webhook-gateway>/webhooks/whk_<ulid>' \
  -d 'hub.topic=https://www.youtube.com/xml/feeds/videos.xml?channel_id=<CHANNEL_ID>' \
  -d 'hub.mode=subscribe'
```

### 5. Data Flow

```
YouTube event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Video metadata (title, description, tags)
- Comments and replies
- Channel activity and subscriptions
- Playlist contents

## Ingest into mem-dog

Data from YouTube flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
