# Zoom

Connect Zoom to memdog to capture meeting recordings, transcripts, and event data.

**Category:** Video & Meetings
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)
3. Your user profile is auto-created on first login

### 2. Connect Zoom

1. In the UI, go to **Settings > Apps**
2. Find **Zoom** under the "Video & Meetings" category
3. Click **Connect**
4. You'll be redirected to Zoom's OAuth consent screen
5. Authorize memdog access and you'll be redirected back
6. The Zoom card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "zoom", "name": "My Zoom Webhook"}'
```

Returns your `inbound_url` (`https://<webhook-gateway>/webhooks/whk_<ulid>`).

### 4. Configure Zoom Webhooks

1. Go to [marketplace.zoom.us](https://marketplace.zoom.us) and select your app
2. Navigate to **Feature > Event Subscriptions**
3. Click **Add Event Subscription**
4. Set the **Event notification endpoint URL** to your `inbound_url`
5. Add event types: `meeting.ended`, `recording.completed`, `recording.transcript_completed`
6. Click **Save**

### 5. Data Flow

```
Zoom event → Webhook Gateway → ZoomAdapter normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (transcription, summarization)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Meeting recordings and transcripts
- Meeting start/end events with participant lists
- Chat messages from meetings
- Cloud recording files (audio, video, transcript)

## Outbound Capabilities

Access Zoom's API via the integration proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/zoom/users/me/meetings \
  -H "Authorization: Bearer <your-jwt>"
```
