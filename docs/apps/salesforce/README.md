# Salesforce

Connect Salesforce to memdog to sync CRM data -- leads, contacts, opportunities, and custom objects.

**Category:** CRM & Sales
**Auth:** OAuth2
**Direction:** Outbound

## Setup

### 1. Login to memdog

1. Go to your memdog UI
2. Click **Sign in with Google** (or use email/password)

### 2. Connect Salesforce

1. In the UI, go to **Settings > Apps**
2. Find **Salesforce** under the "CRM & Sales" category
3. Click **Connect**
4. Log in to your Salesforce org and authorize memdog
5. The Salesforce card should now show **Active**

### 3. Query CRM Data

Salesforce is an outbound integration -- use the integration proxy to query your CRM:

```bash
# Query contacts
curl "https://<your-api>/api/v1/integrations/proxy/salesforce/services/data/v59.0/query?q=SELECT+Id,Name,Email+FROM+Contact+LIMIT+10" \
  -H "Authorization: Bearer <your-jwt>"

# Get a specific account
curl https://<your-api>/api/v1/integrations/proxy/salesforce/services/data/v59.0/sobjects/Account/<account-id> \
  -H "Authorization: Bearer <your-jwt>"

# Search across objects
curl "https://<your-api>/api/v1/integrations/proxy/salesforce/services/data/v59.0/search?q=FIND+%7Bacme%7D+IN+ALL+FIELDS" \
  -H "Authorization: Bearer <your-jwt>"
```

### 4. Ingest CRM Data

Pull Salesforce records and store them in memdog for AI-powered search:

```bash
curl -X POST https://<your-api>/api/v1/data \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Contact: John Doe, VP Sales at Acme Corp. Last activity: demo call 2026-03-15.",
    "source": "salesforce",
    "meta_data": {"sf_object": "Contact", "sf_id": "003xxx"}
  }'
```

## What You Can Access

- Contacts, leads, and accounts
- Opportunities and pipeline data
- Tasks, events, and activity history
- Custom objects and fields
- SOQL and SOSL queries

## Tip: Periodic Sync

Set up a scheduled job to pull recently modified records:

```bash
# Query recently modified opportunities
curl "https://<your-api>/api/v1/integrations/proxy/salesforce/services/data/v59.0/query?q=SELECT+Id,Name,StageName+FROM+Opportunity+WHERE+LastModifiedDate>YESTERDAY" \
  -H "Authorization: Bearer <your-jwt>"
```

Then ingest each record via `POST /api/v1/data` to keep your memdog knowledge base in sync.
