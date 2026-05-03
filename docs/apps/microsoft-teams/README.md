# Microsoft Teams

Connect Microsoft Teams to memdog to ingest channel messages, chats, and meeting data.

**Category:** Chat
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Microsoft Teams

1. In the UI, go to **Settings > Apps**
2. Find **Microsoft Teams** under the "Chat" category
3. Click **Connect**
4. Sign in with your Microsoft account and authorize memdog
5. The Microsoft Teams card should now show **Active**

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "msteams", "name": "My Teams Webhook"}'
```

### 4. Configure Teams Notifications

**Option A: Microsoft Graph Subscriptions (recommended)**

Use the integration proxy to create a change notification subscription:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/microsoft-teams/subscriptions \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "changeType": "created",
    "notificationUrl": "https://<webhook-gateway>/webhooks/whk_<ulid>",
    "resource": "/teams/{team-id}/channels/{channel-id}/messages",
    "expirationDateTime": "2026-04-19T00:00:00Z"
  }'
```

**Option B: Incoming Webhook Connector**

1. In Teams, go to a channel > **Manage Channel > Connectors**
2. Configure an **Outgoing Webhook** pointing to your `inbound_url`

### 5. Data Flow

```
Teams event → Webhook Gateway → MSTeamsAdapter normalizes → NATS queue
→ Webhook Processor → ChannelMessageAgent enriches
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Channel messages and replies
- Direct/group chat messages
- File attachments shared in chats
- Meeting-related notifications

## Outbound Capabilities

Send messages or query Teams data via the integration proxy:

```bash
# Send a message to a channel
curl -X POST "https://<your-api>/api/v1/integrations/proxy/microsoft-teams/teams/{team-id}/channels/{channel-id}/messages" \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"body": {"content": "Hello from memdog!"}}'
```
