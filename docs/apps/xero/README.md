# Xero

Connect Xero to mem-dog to sync invoices, contacts, and accounting data.

**Category:** Finance
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Xero

1. In the UI, go to **Settings > Apps**
2. Find **Xero** under the "Finance" category
3. Click **Connect**
4. Authorize mem-dog via Xero's OAuth consent screen
5. The Xero card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Xero organization.

Query Xero via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/xero/api.xro/2.0/Invoices \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Xero-Tenant-Id: <tenant-id>"
```

For webhooks, configure in the Xero Developer portal.

## What Gets Ingested

- Invoices and credit notes
- Contacts and bank transactions
- Reports and account balances
- Payroll data

## Ingest into mem-dog

Pull data from Xero and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Xero data>",
    "source": "xero",
    "meta_data": {}
  }'
```
