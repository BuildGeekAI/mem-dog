# GitLab

Connect GitLab to memdog to ingest merge requests, issues, and CI/CD events.

**Category:** Dev Tools
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect GitLab

1. In the UI, go to **Settings > Apps**
2. Find **GitLab** under the "Dev Tools" category
3. Click **Connect**
4. Authorize memdog via GitLab's OAuth consent screen
5. The GitLab card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "gitlab", "name": "My GitLab Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure GitLab Events

OAuth2 flow connects to your GitLab instance.

1. Go to your GitLab project **Settings > Webhooks**
2. Set the **URL** to your `inbound_url`
3. Select triggers: Push, Merge Request, Issues, Pipeline
4. Click **Add webhook**

### 5. Data Flow

```
GitLab event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Merge requests and reviews
- Issues and issue comments
- Push events and commits
- CI/CD pipeline events
- Wiki and snippet changes

## Ingest into memdog

Data from GitLab flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
