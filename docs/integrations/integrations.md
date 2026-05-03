# Integration Platform

Powered by [Nango](https://nango.dev) (self-hosted) for OAuth flows, automatic token refresh, credential encryption (AES-256-GCM), and the provider catalog. The API adapter layer preserves the existing endpoint contract while proxying to Nango under the hood.

## Architecture

```
UI (IntegrationsManager)
  → API (/api/v1/integrations) — adapter layer proxies to Nango
    → Nango (nango-server.nango.svc.cluster.local:3003)
      → OAuth flows, token refresh, encrypted credential storage
      → 300+ provider templates (community-maintained)

Webhook Gateway
  → credentials.py — fetches connections from Nango API by end_user_id
  → tag_connection() — channel affinity tagging (business logic, unchanged)
  → /proxy/{provider}/{path} — credential-injecting reverse proxy with ?normalize= transforms
```

### Data flow

1. Provider catalog managed by Nango (community-maintained templates)
2. User browses/connects via OAuth2 popup or API key entry in UI
3. Nango handles the full OAuth flow — authorization, code exchange, token storage, encryption
4. Nango automatically refreshes tokens before they expire
5. When webhooks arrive, gateway fetches connections from Nango by `end_user_id`, tags with channel relevance
6. Clients can call upstream APIs via `/proxy/{provider_key}/{path}` — credentials fetched from Nango and injected

## Nango (self-hosted)

**Namespace:** `nango` | **Services:** nango-server (port 3003), nango-db (Postgres)

Nango manages:
- **Provider catalog** — 300+ provider templates with OAuth URLs, scopes, proxy config
- **OAuth2 flows** — authorization code grant, PKCE, token exchange
- **Token refresh** — automatic, before expiry
- **Credential encryption** — AES-256-GCM with `NANGO_ENCRYPTION_KEY`
- **Connection management** — per-user connections tagged with `end_user_id`

## API Endpoints (`/api/v1/integrations`)

All endpoints are backed by the Nango adapter layer in `api/app/routers/integrations.py`.

**Providers:** List (with category/enabled filter), get, set/clear OAuth credentials.

**Connections:** List (by user/provider), get, delete, create API-key connection.

**OAuth2:** Get authorize URL (creates Nango Connect session), callback (handled by Nango), refresh (no-op — Nango auto-refreshes).

**Credentials:** Get decrypted credentials for a connection (fetched from Nango with auto-refreshed tokens).

## Provider Metadata

Nango doesn't track `app_category`, `capabilities`, or `channel_key` — these are synthesized by the adapter from `api/app/nango_provider_meta.py` (static mapping, ~100 providers).

## Webhook Gateway Integration

After user resolution (from webhook record or identity heuristics), the gateway:
1. Fetches all active connections for the user from Nango API
2. Tags each connection with `relevance` (`channel_match` / `category_match` / `available`)
3. Injects tagged references into `meta_data.integrations` in the envelope

Credentials are never exposed to the webhook processor — only connection references with relevance tags.

## API Proxy

`{METHOD} /proxy/{provider_key}/{path}?user_id={user_id}` — credential-injecting reverse proxy.

- Credentials fetched from Nango (auto-refreshed tokens)
- Retries upstream 429s with exponential backoff (3 attempts)
- Optional `?normalize=contact|calendar_event` for unified response schemas
- No manual token refresh needed — Nango handles it

## Configuration

| Variable | Service | Purpose |
|----------|---------|---------|
| `NANGO_API_URL` | API, Gateway | Nango server URL (in-cluster) |
| `NANGO_SECRET_KEY` | API, Gateway | Nango environment secret key (UUID v4, decrypted from DB) |
| `NANGO_ENCRYPTION_KEY` | Nango | AES-256-GCM key for credential encryption (set once, never rotate) |
| `MASTER_ENCRYPTION_KEY` | API | Fernet key for AI provider API key encryption (unchanged) |

## Setup

1. Deploy Nango: `kubectl apply -f k8s/nango/`
2. Wait for nango-db and nango-server to be ready
3. Decrypt the environment secret key from `_nango_environments` table
4. Set `NANGO_API_URL` and `NANGO_SECRET_KEY` on API and gateway deployments
5. Configure OAuth providers in Nango (via dashboard or `POST /config` API)
6. Navigate to Settings → Apps in the UI
