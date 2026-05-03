# Google Cloud Storage

Connect GCS to mem-dog to sync files and objects from your buckets.

**Category:** Cloud & Storage
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Google Cloud Storage

1. In the UI, go to **Settings > Apps**
2. Find **Google Cloud Storage** under the "Cloud & Storage" category
3. Click **Connect**
4. Authorize mem-dog via Google Cloud Storage's OAuth consent screen
5. The Google Cloud Storage card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow via Google Cloud.

For change notifications:
1. Create a Pub/Sub notification for your bucket
2. Set up a push subscription pointing to your `inbound_url`

## What Gets Ingested

- Object metadata and content
- Pub/Sub notifications for changes
- Bucket access logs

## Ingest into mem-dog

Pull data from Google Cloud Storage and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Google Cloud Storage data>",
    "source": "google-cloud-storage",
    "meta_data": {}
  }'
```
