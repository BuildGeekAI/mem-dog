# Mailchimp

Connect Mailchimp to memdog to sync audience data, campaign stats, and subscriber activity.

**Category:** Email
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Mailchimp

1. In the UI, go to **Settings > Apps**
2. Find **Mailchimp** under the "Email" category
3. Click **Connect**
4. Authorize memdog via Mailchimp's OAuth consent screen
5. The Mailchimp card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Mailchimp account.

For real-time updates, configure Mailchimp webhooks:
1. Go to **Audience > Settings > Webhooks**
2. Set the **Callback URL** to your `inbound_url`
3. Select events: subscribes, unsubscribes, profile updates

## What Gets Ingested

- Campaign performance metrics
- Subscriber activity (opens, clicks)
- Audience/list changes

## Ingest into memdog

Pull data from Mailchimp and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Mailchimp data>",
    "source": "mailchimp",
    "meta_data": {}
  }'
```
