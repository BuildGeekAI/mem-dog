# Workday

Connect Workday to memdog to sync HR, payroll, and organizational data.

**Category:** HR & People
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Workday

1. In the UI, go to **Settings > Apps**
2. Find **Workday** under the "HR & People" category
3. Click **Connect**
4. Authorize memdog via Workday's OAuth consent screen
5. The Workday card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Workday tenant.

Query Workday via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/workday/ccx/api/v1/<tenant>/workers \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Worker profiles and org charts
- Payroll and compensation data
- Time tracking
- Benefits and leave data

## Ingest into memdog

Pull data from Workday and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Workday data>",
    "source": "workday",
    "meta_data": {}
  }'
```
