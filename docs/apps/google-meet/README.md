# Google Meet

Connect Google Meet to mem-dog to access meeting data and recordings.

**Category:** Video & Meetings
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Google Meet

1. In the UI, go to **Settings > Apps**
2. Find **Google Meet** under the "Video & Meetings" category
3. Click **Connect**
4. Authorize mem-dog via Google Meet's OAuth consent screen
5. The Google Meet card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

Google Meet data is accessed via the Google Calendar and Drive APIs.

Google Meet events are tied to Google Calendar:

```bash
# List upcoming meetings
curl https://<your-api>/api/v1/integrations/proxy/google-meet/calendar/v3/calendars/primary/events?q=meet \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Meeting metadata (participants, duration)
- Calendar event details
- Meeting recordings (via Google Drive)

## Ingest into mem-dog

Pull data from Google Meet and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Google Meet data>",
    "source": "google-meet",
    "meta_data": {}
  }'
```
