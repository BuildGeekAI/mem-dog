# Twitter / X

Connect Twitter/X to memdog to ingest tweets, mentions, and engagement data.

**Category:** Social Media
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Twitter / X

1. In the UI, go to **Settings > Apps**
2. Find **Twitter / X** under the "Social Media" category
3. Click **Connect**
4. Authorize memdog via Twitter / X's OAuth consent screen
5. The Twitter / X card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "twitter", "name": "My Twitter / X Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Twitter / X Events

Requires a Twitter Developer account with API v2 access.

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Set up a project and app with OAuth 2.0
3. Configure the **Callback URL** in app settings
4. For real-time data, use Account Activity API webhooks pointing to your `inbound_url`

### 5. Data Flow

```
Twitter / X event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Tweets and retweets
- Mentions and replies
- Direct messages
- Engagement metrics (likes, retweets)

## Ingest into memdog

Data from Twitter / X flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
