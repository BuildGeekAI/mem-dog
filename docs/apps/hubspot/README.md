# HubSpot

Connect HubSpot to mem-dog to sync contacts, deals, and CRM activity.

**Category:** CRM & Sales
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect HubSpot

1. In the UI, go to **Settings > Apps**
2. Find **HubSpot** under the "CRM & Sales" category
3. Click **Connect**
4. Authorize mem-dog via HubSpot's OAuth consent screen
5. The HubSpot card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your HubSpot portal.

Query HubSpot via the integration proxy:

```bash
# List contacts
curl https://<your-api>/api/v1/integrations/proxy/hubspot/crm/v3/objects/contacts \
  -H "Authorization: Bearer <your-jwt>"

# Search deals
curl -X POST https://<your-api>/api/v1/integrations/proxy/hubspot/crm/v3/objects/deals/search \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"filterGroups": [], "limit": 10}'
```

For real-time updates, configure HubSpot webhooks in your app settings.

## What Gets Ingested

- Contacts and companies
- Deals and pipeline stages
- Tickets and conversations
- Email tracking and engagement

## Ingest into mem-dog

Pull data from HubSpot and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<HubSpot data>",
    "source": "hubspot",
    "meta_data": {}
  }'
```
