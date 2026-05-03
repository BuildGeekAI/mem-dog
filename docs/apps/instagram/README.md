# Instagram

Connect Instagram to mem-dog to ingest posts, stories, comments, and mentions.

**Category:** Social Media
**Auth:** OAuth2
**Direction:** Inbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Instagram

1. In the UI, go to **Settings > Apps**
2. Find **Instagram** under the "Social Media" category
3. Click **Connect**
4. Authorize mem-dog via Instagram's OAuth consent screen
5. The Instagram card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "instagram", "name": "My Instagram Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Instagram Events

Requires a Facebook App with Instagram Graph API access.

1. Set up Instagram webhooks via your Facebook App
2. Subscribe to `comments`, `mentions`, and `story_insights`
3. Set the **Callback URL** to your `inbound_url`

### 5. Data Flow

```
Instagram event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Posts and stories
- Comments and mentions
- Direct messages (Business accounts)
- Media metadata

## Ingest into mem-dog

Data from Instagram flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
