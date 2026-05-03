# Google Calendar

Connect Google Calendar to memdog to sync events, schedules, and meeting data.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Google Calendar

1. In the UI, go to **Settings > Apps**
2. Find **Google Calendar** under the "Productivity" category
3. Click **Connect**
4. Authorize memdog via Google Calendar's OAuth consent screen
5. The Google Calendar card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow via Google.

Query calendars via the proxy:

```bash
# List upcoming events
curl https://<your-api>/api/v1/integrations/proxy/google-calendar/calendar/v3/calendars/primary/events?timeMin=2026-03-19T00:00:00Z&maxResults=10&orderBy=startTime&singleEvents=true \
  -H "Authorization: Bearer <your-jwt>"
```

For push notifications, create a watch channel:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/google-calendar/calendar/v3/calendars/primary/events/watch \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"id": "unique-id", "type": "web_hook", "address": "https://<webhook-gateway>/webhooks/whk_<ulid>"}'
```

## What Gets Ingested

- Calendar events and recurring schedules
- Attendee lists and RSVPs
- Meeting links and descriptions
- Free/busy information

## Ingest into memdog

Pull data from Google Calendar and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Google Calendar data>",
    "source": "google-calendar",
    "meta_data": {}
  }'
```
