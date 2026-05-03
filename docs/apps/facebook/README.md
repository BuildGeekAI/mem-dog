# Facebook

Connect Facebook to mem-dog to ingest page posts, comments, and messenger conversations.

**Category:** Social Media
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Facebook

1. In the UI, go to **Settings > Apps**
2. Find **Facebook** under the "Social Media" category
3. Click **Connect**
4. Authorize mem-dog via Facebook's OAuth consent screen
5. The Facebook card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "facebook", "name": "My Facebook Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Facebook Events

Requires a Facebook App with Page and Messenger permissions.

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Set up webhooks under your app
3. Subscribe to `feed`, `messages`, and `messaging_postbacks`
4. Set the **Callback URL** to your `inbound_url`

### 5. Data Flow

```
Facebook event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Page posts and comments
- Messenger conversations
- Reactions and shares
- Page insights and analytics

## Ingest into mem-dog

Data from Facebook flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
