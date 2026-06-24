# Anthropic

Connect Anthropic to mem-dog to use Claude models for enrichment and analysis.

**Category:** Data & AI
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Anthropic

1. In the UI, go to **Settings > Apps**
2. Find **Anthropic** under the "Data & AI" category
3. Click **Connect**
4. Enter your Anthropic API Key when prompted
5. The Anthropic card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your Anthropic API key during setup.

Once connected, Claude is available as an LLM provider. Query via the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/anthropic/v1/messages \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-6-20250514", "max_tokens": 1024, "messages": [{"role": "user", "content": "Hello"}]}'
```

## What Gets Ingested

- API usage data

## Ingest into mem-dog

Pull data from Anthropic and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Anthropic data>",
    "source": "anthropic",
    "meta_data": {}
  }'
```
