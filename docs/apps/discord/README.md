# Discord

Connect Discord to memdog to ingest server messages, threads, and events.

**Category:** Chat
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Discord

1. In the UI, go to **Settings > Apps**
2. Find **Discord** under the "Chat" category
3. Click **Connect**
4. Authorize memdog to access your Discord account
5. The Discord card should now show **Active**

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "discord", "name": "My Discord Webhook"}'
```

### 4. Set Up a Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Create a new application (or select existing)
3. Go to **Bot** and create a bot
4. Under **Privileged Gateway Intents**, enable **Message Content Intent**
5. Go to **OAuth2 > URL Generator**, select `bot` scope with `Read Messages/View Channels` permission
6. Invite the bot to your server using the generated URL

### 5. Configure Event Forwarding

Discord bots receive events via WebSocket (Gateway), not HTTP webhooks. You have two options:

**Option A: Use a relay service** that listens to Discord Gateway events and forwards them to your `inbound_url` as HTTP POSTs.

**Option B: Use Discord's Interactions Endpoint** (for slash commands):
1. In your Discord app settings, set **Interactions Endpoint URL** to your `inbound_url`

### 6. Data Flow

```
Discord event → Webhook Gateway → DiscordAdapter normalizes → NATS queue
→ Webhook Processor → ChannelMessageAgent enriches
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Server channel messages and threads
- Direct messages (if bot has access)
- File attachments and embeds
- Reactions and message metadata

## Outbound Capabilities

Send messages via the integration proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/discord/channels/<channel-id>/messages \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello from memdog!"}'
```
