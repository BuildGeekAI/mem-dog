# Pinecone

Connect Pinecone to mem-dog to use as an external vector database for embeddings.

**Category:** Data & AI
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Pinecone

1. In the UI, go to **Settings > Apps**
2. Find **Pinecone** under the "Data & AI" category
3. Click **Connect**
4. Enter your Pinecone API Key when prompted
5. The Pinecone card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your Pinecone API key during setup.

Query Pinecone via the proxy:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/pinecone/query \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"vector": [0.1, 0.2, ...], "topK": 10, "namespace": "default"}'
```

## What Gets Ingested

- Index stats and metadata

## Ingest into mem-dog

Pull data from Pinecone and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Pinecone data>",
    "source": "pinecone",
    "meta_data": {}
  }'
```
