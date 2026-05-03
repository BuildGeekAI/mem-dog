# Rippling

Connect Rippling to mem-dog to sync employee, payroll, and device management data.

**Category:** HR & People
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Rippling

1. In the UI, go to **Settings > Apps**
2. Find **Rippling** under the "HR & People" category
3. Click **Connect**
4. Authorize mem-dog via Rippling's OAuth consent screen
5. The Rippling card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Rippling account.

Query Rippling via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/rippling/platform/api/employees \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Employee profiles and org structure
- Payroll and time tracking
- Device management data
- App and access provisioning

## Ingest into mem-dog

Pull data from Rippling and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Rippling data>",
    "source": "rippling",
    "meta_data": {}
  }'
```
