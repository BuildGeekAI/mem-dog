# OpenAI

Connect OpenAI to memdog to use GPT models for enrichment and analysis.

**Category:** Data & AI
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect OpenAI

1. In the UI, go to **Settings > Apps**
2. Find **OpenAI** under the "Data & AI" category
3. Click **Connect**
4. Enter your OpenAI API Key when prompted
5. The OpenAI card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your OpenAI API key during setup.

Once connected, OpenAI is available as an LLM provider for the webhook pipeline and AI enrichment. Query via the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/openai/v1/chat/completions \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'
```

## What Gets Ingested

- API usage and billing data

## Ingest into memdog

Pull data from OpenAI and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<OpenAI data>",
    "source": "openai",
    "meta_data": {}
  }'
```
