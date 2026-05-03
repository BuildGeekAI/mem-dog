# Gmail

Connect Gmail to mem-dog to ingest emails, attachments, and threads into your knowledge base.

**Category:** Email
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to mem-dog

1. Go to your mem-dog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Gmail

1. In the UI, go to **Settings > Apps**
2. Find **Gmail** under the "Email" category
3. Click **Connect**
4. Authorize mem-dog to access your Gmail account via Google OAuth
5. The Gmail card should now show **Active**

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "email", "name": "My Gmail Webhook"}'
```

### 4. Configure Gmail Push Notifications

Gmail uses Google Cloud Pub/Sub for push notifications:

1. Create a Pub/Sub topic in your GCP project
2. Grant Gmail publish permissions to the topic
3. Call the Gmail API to watch your mailbox:

```bash
curl -X POST https://gmail.googleapis.com/gmail/v1/users/me/watch \
  -H "Authorization: Bearer <gmail-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "topicName": "projects/<project>/topics/<topic>",
    "labelIds": ["INBOX"]
  }'
```

4. Set up a Pub/Sub push subscription pointing to your `inbound_url`

### 5. Data Flow

```
Gmail notification → Pub/Sub → Webhook Gateway → EmailAdapter normalizes
→ NATS queue → Webhook Processor → enriches (entity extraction, summarization)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Email subject, body (plain text + HTML), and headers
- File attachments (parsed and embedded)
- Thread context and reply chains
- Sender/recipient metadata

## Outbound Capabilities

Send emails or query mailbox via the integration proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/gmail/users/me/messages \
  -H "Authorization: Bearer <your-jwt>"
```
