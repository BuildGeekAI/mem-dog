# Host SaaS — embed mem-dog as a private memory backend

mem-dog can sit behind another product (the **host**). The host owns end-user auth,
billing, and domain UI. mem-dog owns the long-lived corpus, embeddings, search/RAG,
and (optionally) Nango connector credentials.

This guide is the Phase A contract. Full roadmap: [`docs/plans/host-saas-embedding.md`](../plans/host-saas-embedding.md).

## Ownership boundary

| Concern | Owner |
|---------|--------|
| End-user auth, billing, product UI | **Host** |
| Domain SoR (CRM, tickets, CMS) | **Host** |
| Connector Connect UX + sync jobs | **Host** (calls mem-dog APIs) |
| OAuth token vault + provider proxy | **mem-dog (Nango)** |
| Corpus, embeddings, RAG retrieve | **mem-dog** |

**Rule:** Host backends call mem-dog with `x-api-key: md_*` (or the platform `API_KEY` for provisioning). End-user browsers must not hold mem-dog secrets.

## Happy path

```text
1. Host → POST /api/v1/host/workspaces   (platform API_KEY)
2. Host stores { org_id, project_id, user_id, api_key } server-side
3. Host → POST /api/v1/data              (md_* key, tags + project_id)
4. Host → POST /api/v1/ai/embeddings     (optional; or webhook enrich)
5. Host → POST /api/v1/ai/query/semantic { project_id, user_id, query }
```

### 1. Provision a workspace

```bash
curl -s -X POST "$MEMDOG_BASE_URL/api/v1/host/workspaces" \
  -H "x-api-key: $PLATFORM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "external_org_id": "acme-account-1",
    "external_workspace_id": "acme-site-42",
    "display_name": "Acme Workspace"
  }'
```

Response (api_key shown **once** on create):

```json
{
  "org_id": "org_...",
  "project_id": "proj_...",
  "user_id": "...",
  "api_key": "md_...",
  "created": true,
  "external_org_id": "acme-account-1",
  "external_workspace_id": "acme-site-42",
  "display_name": "Acme Workspace"
}
```

Idempotent: same external ids → same workspace, `created=false`, `api_key=null`.

Lookup:

```bash
curl -s "$MEMDOG_BASE_URL/api/v1/host/workspaces?\
external_org_id=acme-account-1&external_workspace_id=acme-site-42" \
  -H "x-api-key: $PLATFORM_API_KEY"
```

### 2. Ingest tagged text

```bash
curl -s -X POST "$MEMDOG_BASE_URL/api/v1/data" \
  -H "x-api-key: $WORKSPACE_MD_KEY" \
  -F "content=Acme pricing is \$29/seat for Pro." \
  -F "name=pricing-note" \
  -F "mime_type=text/plain" \
  -F "owner_user_id=$USER_ID" \
  -F "project_id=$PROJECT_ID" \
  -F "org_id=$ORG_ID" \
  -F "tags=source:host,tenant:acme-site-42,event:note"
```

When `owner_user_id` is the workspace service user, omitted `project_id` /
`org_id` fall back to that user’s defaults.

### 3. Project-scoped semantic search

```bash
curl -s -X POST "$MEMDOG_BASE_URL/api/v1/ai/query/semantic" \
  -H "x-api-key: $WORKSPACE_MD_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"What is Acme Pro pricing?\",
    \"user_id\": \"$USER_ID\",
    \"project_id\": \"$PROJECT_ID\",
    \"max_results\": 5
  }"
```

Empty project → `200` with empty `records` (soft dependency for hosts).

RAG chat accepts the same `project_id` field on `POST /api/v1/ai/query/chat`.

## Tagging conventions (G3)

| Tag / field | Example | Purpose |
|-------------|---------|---------|
| `source:{provider}` | `source:notion` | Connector filters |
| `tenant:{external_id}` | Host workspace id | Defense in depth |
| `connection:{id}` | Host connection row id | Lineage |
| `external_id` | Upstream object id | Upsert (Phase B) |
| `event:{type}` | `event:session` | Domain event write-back |
| `memory_type` | `factual` / `episodic` | Retrieval shaping |

Reserved prefixes: `source:`, `tenant:`, `connection:`, `event:`, `user_id:`, `mime_type:`.
Hosts may add product-specific tags outside these prefixes.

## Auth

| Key | Header | Use |
|-----|--------|-----|
| Platform `API_KEY` | `x-api-key` | `POST/GET /api/v1/host/workspaces` only |
| Workspace `md_*` | `x-api-key` | Data, embeddings, search, integrations |

Local lean often runs with no `API_KEY` (open). Production must set `API_KEY` so workspace provision stays platform-gated.

## Health for host circuit breakers

| Endpoint | Meaning |
|----------|---------|
| `GET /health` | Process up |
| `GET /ready` | Storage singleton constructible (503 if not) |

Hosts should treat memory as optional: timeout or empty hits → degrade feature, do not cascade.

## Tenancy map

| Host concept | mem-dog |
|--------------|---------|
| Billing / customer account | `org_*` |
| Workspace / site / team | `proj_*` |
| Service identity for that workspace | `user_id` + `md_*` |
| End-user RBAC | Enforced by **host** |

## Local verification (Mac mini / lean)

```bash
./scripts/dev-lean.sh up -d
# optional: export API_KEY=dev-platform-key  # if you want provision auth

./scripts/smoke-host-saas.sh
```

Or with pytest:

```bash
cd api && pytest tests/test_host_saas.py -v
```

## Compatibility policy (preview)

- `/api/v1/host/workspaces` and `project_id` on semantic/chat are additive.
- Breaking changes require `/api/v2` or a dated deprecation notice in this doc.
- Standalone mem-dog UI is unchanged; Host SaaS is an embed contract on top.

## Next (Phase B+)

- `external_id` upsert on `/data` and `/ingest`
- Host-driven Nango Connect recipes
- Workspace purge / quotas / key rotation (Phase F)
