# Datadog

Connect Datadog to memdog to sync monitoring data, alerts, and dashboards.

**Category:** Dev Tools
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Datadog

1. In the UI, go to **Settings > Apps**
2. Find **Datadog** under the "Dev Tools" category
3. Click **Connect**
4. Enter your Datadog API Key when prompted
5. The Datadog card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your Datadog API key and application key during setup.

Query Datadog via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/datadog/api/v1/monitor \
  -H "Authorization: Bearer <your-jwt>"
```

For alerts, configure a Datadog webhook integration pointing to your `inbound_url`.

## What Gets Ingested

- Monitor alerts and events
- Metric data
- Log entries
- APM traces

## Ingest into memdog

Pull data from Datadog and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Datadog data>",
    "source": "datadog",
    "meta_data": {}
  }'
```
