# QuickBooks

Connect QuickBooks to memdog to sync invoices, expenses, and accounting data.

**Category:** Finance
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect QuickBooks

1. In the UI, go to **Settings > Apps**
2. Find **QuickBooks** under the "Finance" category
3. Click **Connect**
4. Authorize memdog via QuickBooks's OAuth consent screen
5. The QuickBooks card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your QuickBooks Online company.

Query QuickBooks via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/quickbooks/v3/company/<company-id>/query?query=SELECT%20*%20FROM%20Invoice%20MAXRESULTS%2010 \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, configure in **Apps > Webhooks** in the Intuit Developer portal.

## What Gets Ingested

- Invoices and payments
- Expenses and bills
- Customer and vendor records
- Account balances and reports

## Ingest into memdog

Pull data from QuickBooks and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<QuickBooks data>",
    "source": "quickbooks",
    "meta_data": {}
  }'
```
