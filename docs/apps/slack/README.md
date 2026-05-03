# Slack

Connect Slack to memdog to automatically ingest messages, threads, and files from your workspace.

**Category:** Chat
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI (e.g. `https://memdog-ui-dev-....run.app`)
2. Click **Sign in with Google** (or use email/password)
3. Your user profile is auto-created on first login

### 2. Connect Slack

1. In the UI, go to **Settings > Apps**
2. Find **Slack** under the "Chat" category
3. Click **Connect**
4. You'll be redirected to Slack's OAuth consent screen
5. Select the workspace you want to connect and click **Allow**
6. You'll be redirected back to memdog — the Slack card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango. Tokens are automatically refreshed.

### 3. Create a Webhook Endpoint

1. Call the API to create a per-user webhook:

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "slack", "name": "My Slack Webhook"}'
```

2. The response includes your webhook ID (`whk_<ulid>`) and inbound URL:

```json
{
  "webhook_id": "whk_01ABC...",
  "inbound_url": "https://<webhook-gateway>/webhooks/whk_01ABC..."
}
```

### 4. Configure Slack Event Subscriptions

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and select your app
2. Navigate to **Event Subscriptions** and toggle **Enable Events**
3. Set the **Request URL** to your `inbound_url` from step 3
4. Under **Subscribe to bot events**, add the events you want (e.g. `message.channels`, `message.groups`, `message.im`)
5. Click **Save Changes**

### 5. Data Flow

```
Slack event → Webhook Gateway → SlackAdapter normalizes → NATS queue
→ Webhook Processor → ChannelMessageAgent enriches (entities, sentiment, intent)
→ API stores in Postgres + pgvector + Neo4j
```

Your Slack messages are now searchable via vector, full-text, hybrid, graph, or full search modes.

## What Gets Ingested

- Channel messages and threads
- Direct messages
- File attachments (text extracted, embeddings generated)
- Reactions and metadata

## Outbound Capabilities

memdog can also call Slack's API on your behalf via the integration proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/slack/chat.postMessage \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel": "C01ABC", "text": "Hello from memdog!"}'
```
