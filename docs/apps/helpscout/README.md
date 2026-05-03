# Help Scout

Connect Help Scout to memdog to sync mailbox conversations and customer data.

**Category:** Customer Support
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Help Scout

1. In the UI, go to **Settings > Apps**
2. Find **Help Scout** under the "Customer Support" category
3. Click **Connect**
4. Authorize memdog via Help Scout's OAuth consent screen
5. The Help Scout card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Help Scout account.

Query Help Scout via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/helpscout/v2/conversations \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, go to **Manage > Apps > Webhooks** and point to your `inbound_url`.

## What Gets Ingested

- Conversations and threads
- Customer profiles
- Mailbox and folder data
- Satisfaction ratings

## Ingest into memdog

Pull data from Help Scout and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Help Scout data>",
    "source": "helpscout",
    "meta_data": {}
  }'
```
