# Google Drive

Connect Google Drive to memdog to sync documents, spreadsheets, and files into your knowledge base.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Google Drive

1. In the UI, go to **Settings > Apps**
2. Find **Google Drive** under the "Productivity" category
3. Click **Connect**
4. Authorize memdog to access your Google Drive
5. The Google Drive card should now show **Active**

### 3. Sync Content

Google Drive is an outbound integration -- memdog pulls files via the Drive API through the integration proxy:

```bash
# List recent files
curl https://<your-api>/api/v1/integrations/proxy/google-drive/files?orderBy=modifiedTime%20desc \
  -H "Authorization: Bearer <your-jwt>"

# Get file metadata
curl https://<your-api>/api/v1/integrations/proxy/google-drive/files/<file-id> \
  -H "Authorization: Bearer <your-jwt>"

# Export a Google Doc as plain text
curl "https://<your-api>/api/v1/integrations/proxy/google-drive/files/<file-id>/export?mimeType=text/plain" \
  -H "Authorization: Bearer <your-jwt>"
```

### 4. Optional: Push Notifications

Google Drive supports push notifications for file changes:

1. Set up a webhook channel via the Drive API:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/google-drive/changes/watch \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "unique-channel-id",
    "type": "web_hook",
    "address": "https://<webhook-gateway>/webhooks/whk_<ulid>"
  }'
```

2. Drive will POST change notifications to your webhook endpoint

## What You Can Access

- Google Docs, Sheets, Slides (exported as text/CSV)
- PDFs, images, and other uploaded files
- Shared drives and team content
- File metadata, permissions, and revision history

## Tip: Bulk Ingest

To ingest multiple Drive files into memdog:

```bash
# Fetch file list, then ingest each via the data API
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<file content>",
    "source": "google-drive",
    "meta_data": {"drive_file_id": "<file-id>", "filename": "doc.pdf"}
  }'
```
