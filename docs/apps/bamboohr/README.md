# BambooHR

Connect BambooHR to memdog to sync employee data, time-off, and HR workflows.

**Category:** HR & People
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect BambooHR

1. In the UI, go to **Settings > Apps**
2. Find **BambooHR** under the "HR & People" category
3. Click **Connect**
4. Authorize memdog via BambooHR's OAuth consent screen
5. The BambooHR card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your BambooHR subdomain.

Query BambooHR via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/bamboohr/api/gateway.php/<company>/v1/employees/directory \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks, configure in BambooHR under **Account > Webhooks**.

## What Gets Ingested

- Employee directory and profiles
- Time-off requests and balances
- Job and salary information
- Custom reports

## Ingest into memdog

Pull data from BambooHR and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<BambooHR data>",
    "source": "bamboohr",
    "meta_data": {}
  }'
```
