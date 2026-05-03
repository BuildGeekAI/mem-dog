# Azure Blob Storage

Connect Azure Blob Storage to memdog to sync files and container data.

**Category:** Cloud & Storage
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Azure Blob Storage

1. In the UI, go to **Settings > Apps**
2. Find **Azure Blob Storage** under the "Cloud & Storage" category
3. Click **Connect**
4. Authorize memdog via Azure Blob Storage's OAuth consent screen
5. The Azure Blob Storage card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow via Azure AD.

For blob event notifications:
1. Create an Event Grid subscription on your storage account
2. Set the endpoint to your `inbound_url`

## What Gets Ingested

- Blob metadata and content
- Event Grid notifications
- Container access logs

## Ingest into memdog

Pull data from Azure Blob Storage and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Azure Blob Storage data>",
    "source": "azure-blob",
    "meta_data": {}
  }'
```
