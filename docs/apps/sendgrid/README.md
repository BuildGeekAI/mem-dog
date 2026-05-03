# SendGrid

Connect SendGrid to memdog for transactional email sending and delivery tracking.

**Category:** Email
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect SendGrid

1. In the UI, go to **Settings > Apps**
2. Find **SendGrid** under the "Email" category
3. Click **Connect**
4. Enter your SendGrid API Key when prompted
5. The SendGrid card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your SendGrid API key during connection setup.

For inbound events, configure SendGrid's **Event Webhook**:
1. Go to **Settings > Mail Settings > Event Webhook**
2. Set the **HTTP Post URL** to your `inbound_url`
3. Select events: Delivered, Opened, Clicked, Bounced

## What Gets Ingested

- Email delivery events (via Event Webhook)
- Bounce and spam reports
- Open and click tracking

## Ingest into memdog

Pull data from SendGrid and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<SendGrid data>",
    "source": "sendgrid",
    "meta_data": {}
  }'
```
