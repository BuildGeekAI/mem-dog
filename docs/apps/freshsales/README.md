# Freshsales

Connect Freshsales to mem-dog to sync contacts, deals, and sales activity.

**Category:** CRM & Sales
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Freshsales

1. In the UI, go to **Settings > Apps**
2. Find **Freshsales** under the "CRM & Sales" category
3. Click **Connect**
4. Authorize mem-dog via Freshsales's OAuth consent screen
5. The Freshsales card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Freshworks account.

Query Freshsales via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/freshsales/api/contacts \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Contacts and accounts
- Deals and pipeline stages
- Tasks and appointments
- Sales activity logs

## Ingest into mem-dog

Pull data from Freshsales and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Freshsales data>",
    "source": "freshsales",
    "meta_data": {}
  }'
```
