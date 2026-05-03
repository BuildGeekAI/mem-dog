# Zoho CRM

Connect Zoho CRM to memdog to sync leads, contacts, deals, and custom modules.

**Category:** CRM & Sales
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Zoho CRM

1. In the UI, go to **Settings > Apps**
2. Find **Zoho CRM** under the "CRM & Sales" category
3. Click **Connect**
4. Authorize memdog via Zoho CRM's OAuth consent screen
5. The Zoho CRM card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Zoho account.

Query Zoho CRM via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/zoho-crm/crm/v2/Leads \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Leads and contacts
- Deals and quotes
- Tasks and events
- Custom module records

## Ingest into memdog

Pull data from Zoho CRM and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Zoho CRM data>",
    "source": "zoho-crm",
    "meta_data": {}
  }'
```
