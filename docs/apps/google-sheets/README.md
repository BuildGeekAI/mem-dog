# Google Sheets

Connect Google Sheets to mem-dog to sync spreadsheet data into your knowledge base.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Google Sheets

1. In the UI, go to **Settings > Apps**
2. Find **Google Sheets** under the "Productivity" category
3. Click **Connect**
4. Authorize mem-dog via Google Sheets's OAuth consent screen
5. The Google Sheets card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow via Google.

Query sheets via the proxy:

```bash
# Read a range
curl https://<your-api>/api/v1/integrations/proxy/google-sheets/v4/spreadsheets/<sheet-id>/values/Sheet1!A1:D10 \
  -H "Authorization: Bearer <your-jwt>"
```

## What Gets Ingested

- Spreadsheet cell data
- Named ranges and formulas
- Sheet metadata
- Charts and pivot tables

## Ingest into mem-dog

Pull data from Google Sheets and store in mem-dog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Google Sheets data>",
    "source": "google-sheets",
    "meta_data": {}
  }'
```
