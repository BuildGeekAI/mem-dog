# Host SaaS — embed mem-dog as a private memory backend

mem-dog can sit behind another product (the **host**). The host owns end-user auth,
billing, and domain UI. mem-dog owns the long-lived corpus, embeddings, search/RAG,
and (optionally) Nango connector credentials.

This guide is the Host SaaS contract (Phases A–B + F3 observability). Full roadmap: [`docs/plans/host-saas-embedding.md`](../plans/host-saas-embedding.md).

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
| `external_id` (form / envelope) | Upstream object id | Upsert (see below) |
| `event:{type}` | `event:session` | Domain event write-back |
| `memory_type` | `factual` / `episodic` | Retrieval shaping |

Reserved prefixes: `source:`, `tenant:`, `connection:`, `event:`, `user_id:`, `mime_type:`, `external_id:`.
Hosts may add product-specific tags outside these prefixes.

## External ID upsert (Phase B)

Re-syncing the same upstream object must not create duplicates.

| Field | Where | Notes |
|-------|--------|--------|
| `external_id` | `POST /api/v1/data` form | Unique per `project_id` when set, else per owner `user_id` |
| `context.external_id` | `POST /api/v1/ingest` envelope | Same rules on `direct=true` store |

**Behavior**

1. First write with `external_id` → new `data_id`, `created=true`, `updated=false`
2. Later write with the same `(project_id|owner, external_id)` → same `data_id`, new version, `created=false`, `updated=true`
3. Response shape: `{ data_id, version, message, created, updated }`
4. Metadata stores `external_id`; a tag `external_id:{value}` is auto-added for search

**Example (form)**

```bash
curl -X POST "$BASE/api/v1/data" \
  -H "x-api-key: $MD_KEY" \
  -F "content=Updated page body" \
  -F "mime_type=text/plain" \
  -F "owner_user_id=$USER_ID" \
  -F "org_id=$ORG_ID" \
  -F "project_id=$PROJ_ID" \
  -F "external_id=notion:page-abc"
```

**Example (ingest direct)**

```json
{
  "direct": true,
  "envelope": {
    "origin": { "source_type": "other" },
    "content_text": "Updated page body",
    "context": {
      "org_id": "org_…",
      "project_id": "proj_…",
      "external_id": "notion:page-abc",
      "tags": ["source:notion"]
    }
  }
}
```

## Auth

| Key | Header | Use |
|-----|--------|-----|
| Platform `API_KEY` | `x-api-key` | `POST/GET /api/v1/host/workspaces`, provider OAuth app credentials |
| Workspace `md_*` | `x-api-key` | Data, embeddings, search, connections, webhooks |

Local lean often runs with no `API_KEY` (open). Production must set `API_KEY` so workspace provision stays platform-gated.

**Integrations scoping:** `md_*` / JWT callers only see and mutate their own Nango connections (auto-scoped). Platform key may filter by `user_id` or list all (gateway/admin).

### Request correlation (F3)

Send `X-Request-Id` on host → mem-dog calls (or omit to receive a generated UUID). The API echoes the same value on every response and includes it in structured errors:

```json
{
  "detail": "…",
  "error": {
    "code": "not_found",
    "message": "…",
    "details": {},
    "request_id": "…"
  }
}
```

**Client tip:** keep reading top-level `detail` (FastAPI-compatible). The `error` object is additive. Strict schemas that reject unknown properties (`additionalProperties: false`) should allow `error` or only validate `detail`.

## Recipe: file / CSV sync (no Nango)

Host SoR remains the source of truth. mem-dog stores searchable memory with upsert.

```bash
# 1) Provision once (platform key)
# → org_id, project_id, user_id, md_*

# 2) For each upstream row / file revision:
curl -s -X POST "$MEMDOG_BASE_URL/api/v1/data" \
  -H "x-api-key: $WORKSPACE_MD_KEY" \
  -H "X-Request-Id: host-sync-$(date +%s)" \
  -F "content@$CSV_OR_TEXT_PATH" \
  -F "name=customers-export.csv" \
  -F "mime_type=text/csv" \
  -F "owner_user_id=$USER_ID" \
  -F "org_id=$ORG_ID" \
  -F "project_id=$PROJECT_ID" \
  -F "external_id=csv:customers:v1" \
  -F "tags=source:host,tenant:acme-site-42,event:sync"

# Re-upload the same external_id after SoR changes → same data_id, new version.

# 3) Embed (optional) then search
curl -s -X POST "$MEMDOG_BASE_URL/api/v1/ai/embeddings" \
  -H "x-api-key: $WORKSPACE_MD_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"data_id\":\"$DATA_ID\",\"user_id\":\"$USER_ID\",\"project_id\":\"$PROJECT_ID\"}"

curl -s -X POST "$MEMDOG_BASE_URL/api/v1/ai/query/semantic" \
  -H "x-api-key: $WORKSPACE_MD_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"enterprise customers in EMEA\",\"user_id\":\"$USER_ID\",\"project_id\":\"$PROJECT_ID\",\"max_results\":5}"
```

## Connect & integrations (Phase B)

Hosts drive Nango from the **server** with the workspace `md_*` key. Never put `md_*` in browsers.

| Step | Call | Key |
|------|------|-----|
| List providers | `GET /api/v1/integrations/providers` | `md_*` |
| Start Connect session | `POST /api/v1/integrations/oauth/connect-session` `{"provider_key":"notion"}` | `md_*` |
| Or redirect OAuth URL | `GET /api/v1/integrations/oauth/authorize/{provider}` | `md_*` (user defaults to key owner) |
| List connections | `GET /api/v1/integrations/connections` | `md_*` (auto-scoped) |
| API-key provider | `POST /api/v1/integrations/connections/api-key` | `md_*` |
| Inbound webhooks | `POST /api/v1/webhooks` → `whk_*` URL on gateway | `md_*` |
| Outbound provider API | `{GATEWAY}/proxy/{provider}/{path}?user_id=…` | `WGW_API_KEY` |

Sync job pattern: gateway proxy → normalize → `POST /api/v1/data` with `external_id` + `project_id`.

## API key rotation (Phase F5)

Hosts rotate without re-provisioning the workspace.

| Call | Auth | Notes |
|------|------|-------|
| `GET /api/v1/host/api-keys` | `md_*` | Lists `key_id`, `name`, `key_prefix`, `last_used_at` — never raw key |
| `POST /api/v1/host/api-keys` | `md_*` | Create additional key (raw key once) |
| `POST /api/v1/host/api-keys/rotate` | `md_*` | Create new; optional `revoke_key_id` |
| `DELETE /api/v1/host/api-keys/{key_id}` | `md_*` | Revoke; refuses last key unless `allow_empty=true` |

Platform `API_KEY` may pass `user_id` (query or body) to manage any workspace user.

**Recommended flow**

1. `POST /api/v1/host/api-keys/rotate` with `{"name":"host-rotated"}` → store new `key`
2. Switch host backends to the new key
3. `POST /api/v1/host/api-keys/rotate` with `{"name":"host-rotated","revoke_key_id":"<old>"}`  
   or `DELETE /api/v1/host/api-keys/{old_key_id}`

Same-call rotate (create + revoke) is fine once the new key is persisted.

## Workspace purge & export (Phase F1)

Platform key only. Sync purge is L0 (fine for laptop-sized workspaces; large tenants may need async later).

| Call | Notes |
|------|-------|
| `GET /api/v1/host/workspaces/export?external_org_id=&external_workspace_id=` | Manifest of data/memory ids (no blobs) |
| `DELETE /api/v1/host/workspaces?external_org_id=&external_workspace_id=` | Purge data, memories, keys, org/project, index |
| `DELETE /api/v1/host/workspaces/by-project/{project_id}` | Same purge via `project_id` |

Query flags: `delete_connections=true` (Nango), `delete_service_user=true` (default).

Idempotent: re-delete returns `already_gone=true`, `purged=true`.

```bash
curl -s -X DELETE "$MEMDOG_BASE_URL/api/v1/host/workspaces?\
external_org_id=acme-account-1&external_workspace_id=acme-site-42" \
  -H "x-api-key: $PLATFORM_API_KEY"
```

## Quotas (Phase F2)

Defaults are **off** (`0`) so lean/local stays unrestricted. Set env on the API to enforce:

| Env | Meaning |
|-----|---------|
| `QUOTA_INGEST_RPM` | Max POST/PUT ingest requests per minute per tenant (`user:` / `key:` / `ip:`) |
| `QUOTA_MAX_BODY_BYTES` | Max request body (Content-Length + actual upload size) |
| `QUOTA_MAX_STORAGE_BYTES_PER_PROJECT` | Max sum of data sizes in a project for the owner |

Applies to `/api/v1/data`, `/api/v1/ingest`, embeddings create, and user data uploads.

Over limit → `429` with `Retry-After` and:

```json
{
  "detail": { "code": "rate_limited", "message": "…", "details": {} },
  "error": { "code": "rate_limited", "message": "…", "details": {}, "request_id": "…" }
}
```

(`quota_exceeded` for body/storage limits.)

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

## Compatibility policy

`/api/v1` is the Host SaaS stable surface for this embed contract.

| Change type | Policy |
|-------------|--------|
| Additive fields, new optional query/body params, new host routes under `/api/v1/host` | Allowed without major bump |
| Renamed/removed required fields, auth header changes, semantic of `project_id` / `external_id` | Requires `/api/v2` **or** a dated deprecation notice in this doc (≥90 days) |
| Error shape | `error.{code,message,details,request_id}` is stable; top-level `detail` retained for compatibility |
| OAuth authorize without `user_id` (open/global caller) | Returns **400** (`user_id is required`) rather than FastAPI **422** validation |

Stable host capabilities today: workspace provision/lookup, project-scoped semantic search, `external_id` upsert, `X-Request-Id`, structured errors, API-key create/list/rotate/revoke, workspace export/purge, env-gated quotas.

Standalone mem-dog UI is unchanged; Host SaaS is an embed contract on top.

### Pin a client

| Language | Package | Pin (Host SaaS F4) |
|----------|---------|-------------------|
| Python | `mem-dog-client` | `==0.1.1` |
| TypeScript | `@mem-dog/client` | `0.2.1` |

Install from this repo (`clients/python`, `clients/typescript`) until packages are published. Both SDKs send `x-api-key` (and Bearer) for `api_key` / `apiKey`.

### SDK method map

| Host flow | HTTP | Python | TypeScript |
|-----------|------|--------|------------|
| Provision workspace | `POST /api/v1/host/workspaces` | `create_host_workspace` | `createHostWorkspace` |
| Lookup workspace | `GET /api/v1/host/workspaces` | `get_host_workspace` | `getHostWorkspace` |
| Upsert by external id | `POST /api/v1/data` + `external_id` | `upsert_data` | `upsertData` |
| Project-scoped search | `POST /api/v1/ai/query/semantic` | `semantic_search(..., project_id=)` | `semanticSearch(..., { projectId })` |
| Rotate API key | `POST /api/v1/host/api-keys/rotate` | `rotate_host_api_key` | `rotateHostApiKey` |
| Export / purge | `GET .../export`, `DELETE .../workspaces` | `export_host_workspace` / `purge_host_workspace` | `exportHostWorkspace` / `purgeHostWorkspace` |

OpenAPI tag **Host SaaS** (operations marked `x-host-saas: true`) is for codegen filters.

## Next (Phase F)

- Notion / Slack Connect recipes (need Nango)
- Async purge job + full archive export for large workspaces
