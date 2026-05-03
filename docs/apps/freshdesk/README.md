# Freshdesk

Connect Freshdesk to mem-dog to sync support tickets and customer interactions.

**Category:** Customer Support
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Freshdesk

1. In the UI, go to **Settings > Apps**
2. Find **Freshdesk** under the "Customer Support" category
3. Click **Connect**
4. Authorize mem-dog via Freshdesk's OAuth consent screen
5. The Freshdesk card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Freshworks account.

Query Freshdesk via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/freshdesk/api/v2/tickets \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, create an automation rule in Freshdesk that POSTs to your `inbound_url`.

## What Gets Ingested

- Tickets and conversations
- Contact and company data
- Knowledge base articles
- Canned responses

## Ingest into mem-dog

Pull data from Freshdesk and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Freshdesk data>",
    "source": "freshdesk",
    "meta_data": {}
  }'
```
