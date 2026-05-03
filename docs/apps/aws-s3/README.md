# AWS S3

Connect AWS S3 to mem-dog to sync files and objects from your buckets.

**Category:** Cloud & Storage
**Auth:** API Key
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect AWS S3

1. In the UI, go to **Settings > Apps**
2. Find **AWS S3** under the "Cloud & Storage" category
3. Click **Connect**
4. Enter your AWS S3 API Key when prompted
5. The AWS S3 card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango.

### 3. Access Data

Provide your AWS access key ID and secret access key during setup.

For S3 event notifications to mem-dog:
1. Go to your S3 bucket **Properties > Event notifications**
2. Create an event notification targeting an SNS topic or Lambda
3. Forward events to your `inbound_url`

## What Gets Ingested

- Object metadata and content
- Bucket event notifications
- Access logs

## Ingest into mem-dog

Pull data from AWS S3 and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<AWS S3 data>",
    "source": "aws-s3",
    "meta_data": {}
  }'
```
