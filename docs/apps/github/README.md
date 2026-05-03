# GitHub

Connect GitHub to memdog to ingest issues, pull requests, commits, and repository events.

**Category:** Dev Tools
**Auth:** OAuth2
**Direction:** Inbound + Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect GitHub

1. In the UI, go to **Settings > Apps**
2. Find **GitHub** under the "Dev Tools" category
3. Click **Connect**
4. Authorize memdog via GitHub OAuth
5. The GitHub card should now show **Active**

### 3. Create a Webhook Endpoint

```bash
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "github", "name": "My GitHub Webhook"}'
```

### 4. Configure GitHub Webhooks

1. Go to your repository (or organization) **Settings > Webhooks**
2. Click **Add webhook**
3. Set **Payload URL** to your `inbound_url`
4. Set **Content type** to `application/json`
5. Optionally set a **Secret** (matches the signing secret from webhook creation)
6. Select events: `Push`, `Pull requests`, `Issues`, `Issue comments`, `Pull request reviews`
7. Click **Add webhook**

### 5. Data Flow

```
GitHub event → Webhook Gateway → normalizes → NATS queue
→ Webhook Processor → sub-agent enriches (code analysis, entity extraction)
→ API stores in Postgres + pgvector + Neo4j
```

## What Gets Ingested

- Issues and issue comments
- Pull requests, reviews, and review comments
- Push events with commit details
- Release and deployment events
- Repository metadata

## Outbound Capabilities

Access GitHub's API via the integration proxy:

```bash
curl https://<your-api>/api/v1/integrations/proxy/github/repos/owner/repo/issues \
  -H "Authorization: Bearer <your-jwt>"
```
