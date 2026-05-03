# Reddit

Connect Reddit to mem-dog to ingest subreddit posts, comments, and discussions.

**Category:** Social Media
**Auth:** OAuth2
**Direction:** Inbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Reddit

1. In the UI, go to **Settings > Apps**
2. Find **Reddit** under the "Social Media" category
3. Click **Connect**
4. Authorize mem-dog via Reddit's OAuth consent screen
5. The Reddit card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "reddit", "name": "My Reddit Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Reddit Events

Requires a Reddit app (script or web type).

Reddit doesn't support native webhooks. Use polling via the proxy:

```bash
# Get recent posts from a subreddit
curl https://<your-api>/api/v1/integrations/proxy/reddit/r/programming/new.json?limit=25 \
  -H "Authorization: Bearer <your-jwt>"
```

### 5. Data Flow

```
Reddit event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Subreddit posts and self-posts
- Comments and reply threads
- Upvote/downvote metadata
- Cross-posts and links

## Ingest into mem-dog

Data from Reddit flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
