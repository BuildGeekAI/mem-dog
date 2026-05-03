# Mailgun

Connect Mailgun to mem-dog for email sending and delivery event tracking.

**Category:** Email
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Mailgun

1. In the UI, go to **Settings > Apps**
2. Find **Mailgun** under the "Email" category
3. Click **Connect**
4. Enter your Mailgun API Key when prompted
5. The Mailgun card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your Mailgun API key and domain during setup.

For inbound events, configure Mailgun webhooks:
1. Go to **Sending > Webhooks**
2. Add your `inbound_url` for desired event types

## What Gets Ingested

- Delivery and bounce events
- Inbound email routing
- Open and click tracking

## Ingest into mem-dog

Pull data from Mailgun and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Mailgun data>",
    "source": "mailgun",
    "meta_data": {}
  }'
```
