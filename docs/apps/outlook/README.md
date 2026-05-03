# Outlook

Connect Outlook to memdog to ingest emails, calendar events, and attachments.

**Category:** Email
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Outlook

1. In the UI, go to **Settings > Apps**
2. Find **Outlook** under the "Email" category
3. Click **Connect**
4. Authorize memdog via Outlook's OAuth consent screen
5. The Outlook card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "email", "name": "My Outlook Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Outlook Events

Uses Microsoft Graph API subscriptions for real-time notifications.

1. Create a Graph API subscription via the integration proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/outlook/subscriptions \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "changeType": "created",
    "notificationUrl": "https://<webhook-gateway>/webhooks/whk_<ulid>",
    "resource": "me/mailFolders('Inbox')/messages",
    "expirationDateTime": "2026-04-19T00:00:00Z"
  }'
```

### 5. Data Flow

```
Outlook event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (entity extraction, embeddings)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Emails with full body and headers
- File attachments
- Calendar events and invites
- Contact data

## Ingest into memdog

Data from Outlook flows automatically through the webhook pipeline. Each event is:
1. Normalized into Universal Envelope format
2. Routed to a specialized sub-agent based on content type
3. Enriched with entity extraction, sentiment, and embeddings
4. Stored in Postgres + pgvector for AI-powered search
