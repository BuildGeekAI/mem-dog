# Jira

Connect Jira to memdog to sync issues, projects, and workflow data into your knowledge base.

**Category:** Productivity
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Jira

1. In the UI, go to **Settings > Apps**
2. Find **Jira** under the "Productivity" category
3. Click **Connect**
4. Authorize memdog to access your Atlassian account
5. Select the Jira site you want to connect
6. The Jira card should now show **Active**

### 3. Query Issues

Jira is an outbound integration -- use the integration proxy to query your projects:

```bash
# Search issues with JQL
curl "https://<your-api>/api/v1/integrations/proxy/jira/rest/api/3/search?jql=project=ENG+AND+status!=Done+ORDER+BY+updated+DESC" \
  -H "Authorization: Bearer <your-jwt>"

# Get a specific issue
curl https://<your-api>/api/v1/integrations/proxy/jira/rest/api/3/issue/ENG-123 \
  -H "Authorization: Bearer <your-jwt>"

# Get all projects
curl https://<your-api>/api/v1/integrations/proxy/jira/rest/api/3/project \
  -H "Authorization: Bearer <your-jwt>"
```

### 4. Optional: Webhook for Real-Time Updates

Set up a Jira webhook to push events to memdog:

1. In Jira, go to **Settings > System > WebHooks**
2. Click **Create a WebHook**
3. Set the URL to your memdog webhook endpoint:

```bash
# First create a webhook endpoint
curl -X POST https://<your-api>/api/v1/webhooks \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "jira", "name": "My Jira Webhook"}'
```

4. Use the returned `inbound_url` as the Jira webhook URL
5. Select events: `Issue created`, `Issue updated`, `Comment created`
6. Click **Create**

### 5. Ingest Issues

Store Jira data in memdog for AI-powered search:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "ENG-123: Fix login timeout bug. Status: In Progress. Assignee: jane@acme.com",
    "source": "jira",
    "meta_data": {"jira_key": "ENG-123", "project": "ENG"}
  }'
```

## What You Can Access

- Issues with full details (description, comments, attachments)
- Projects and boards
- Sprints and backlogs
- Workflow statuses and transitions
- JQL search across all data
