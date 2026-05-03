# Trello

Connect Trello to memdog to sync boards, cards, and team activity.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Trello

1. In the UI, go to **Settings > Apps**
2. Find **Trello** under the "Productivity" category
3. Click **Connect**
4. Authorize memdog via Trello's OAuth consent screen
5. The Trello card should now show **Active**

Credentials are stored encrypted (AES-256-GCM) via Nango with automatic token refresh.

### 3. Access Data

OAuth2 flow connects to your Trello account.

Query Trello via the proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/trello/1/boards/<board-id>/cards \
  -H "Authorization: Bearer <your-jwt>"
```

For webhooks:

```bash
curl -X POST https://<your-api>/api/v1/integrations/proxy/trello/1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"callbackURL": "https://<webhook-gateway>/webhooks/whk_<ulid>", "idModel": "<board-id>"}'
```

## What Gets Ingested

- Boards and lists
- Cards with descriptions and checklists
- Comments and attachments
- Member activity

## Ingest into memdog

Pull data from Trello and store in memdog:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<Trello data>",
    "source": "trello",
    "meta_data": {}
  }'
```
