# Pipedrive

Connect Pipedrive to mem-dog to sync deals, contacts, and sales pipeline data.

**Category:** CRM & Sales
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Pipedrive

1. In the UI, go to **Settings > Apps**
2. Find **Pipedrive** under the "CRM & Sales" category
3. Click **Connect**
4. Authorize mem-dog via Pipedrive's OAuth consent screen
5. The Pipedrive card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Pipedrive account.

Query Pipedrive via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/pipedrive/v1/deals \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, configure in **Settings > Webhooks** in Pipedrive.

## What Gets Ingested

- Deals and pipeline stages
- Persons and organizations
- Activities and notes
- Email tracking

## Ingest into mem-dog

Pull data from Pipedrive and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Pipedrive data>",
    "source": "pipedrive",
    "meta_data": {}
  }'
```
