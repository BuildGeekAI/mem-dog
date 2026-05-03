# OneDrive

Connect OneDrive to mem-dog to sync files and documents from your Microsoft account.

**Category:** Cloud & Storage
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect OneDrive

1. In the UI, go to **Settings > Apps**
2. Find **OneDrive** under the "Cloud & Storage" category
3. Click **Connect**
4. Authorize mem-dog via OneDrive's OAuth consent screen
5. The OneDrive card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow via Microsoft.

Query OneDrive via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/onedrive/me/drive/root/children \
  -H "Authorization: Bearer <your-jwt>"
```

For change notifications, create a Microsoft Graph subscription pointing to your `inbound_url`.

## What Gets Ingested

- Files and folder structure
- Shared items and permissions
- Recent activity
- Office document content

## Ingest into mem-dog

Pull data from OneDrive and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<OneDrive data>",
    "source": "onedrive",
    "meta_data": {}
  }'
```
