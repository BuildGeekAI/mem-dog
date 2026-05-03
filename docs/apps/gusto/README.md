# Gusto

Connect Gusto to memdog to sync payroll, employee, and benefits data.

**Category:** HR & People
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Gusto

1. In the UI, go to **Settings > Apps**
2. Find **Gusto** under the "HR & People" category
3. Click **Connect**
4. Authorize memdog via Gusto's OAuth consent screen
5. The Gusto card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Gusto company.

Query Gusto via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/gusto/v1/companies/<company-id>/employees \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Employee profiles
- Payroll runs and pay stubs
- Benefits enrollment
- Company and location data

## Ingest into memdog

Pull data from Gusto and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Gusto data>",
    "source": "gusto",
    "meta_data": {}
  }'
```
