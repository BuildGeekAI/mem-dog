# Deployment Paths

mem-dog supports **three deployment targets, maintained in parallel**:

| Path | Estate | Primary use |
|------|--------|-------------|
| **Local** | `docker compose`, one machine | Development on a laptop; no cloud account needed |
| **GKE-centric** | Cluster `open-jaw`, project `memdog-dev` | Shared dev; any deployment needing GPUs, PVCs, or in-VPC data residency |
| **Cloud-centric** | Cloud Run + managed services, project `memdog-prod` | Production; scale-to-zero economics, no cluster to operate |

None replaces the others. See [Local Development](local-dev.md),
[GKE Implementation](../gke/implementation.md), and
[GCP Production Implementation](../gcp/prod/implementation.md) for each path in full.

The local path is the cheapest place to catch a seam violation: it uses a **third** value for
most seams, so a change hardcoded to either cloud path usually breaks `docker compose` first.

---

## The governing rule

> **One codebase, two deployment targets. Divergence lives behind a runtime seam — never in
> forked code, and never in a deleted asset.**

A change made for one path must leave the other working. Concretely this forbids three things
that a single-target migration would otherwise do:

1. **Deleting manifests.** In-cluster Ollama, GoTrue, and openclaw-node stay in `k8s/`. The
   Cloud path does not deploy them; it does not remove them.
2. **Replacing an implementation in place.** Auth is the sharp case: swapping HS256 for RS256
   in `api/main.py` breaks GKE the moment it deploys. Both verifiers ship; config selects one.
3. **Editing shared config for one estate.** `config/ai.env` is a single file today, so a
   prod-motivated edit silently changes dev. It must be split before the Cloud path is built.

---

## Divergence matrix

Everything that differs between paths, and the seam that selects it.

| Concern | Seam | Local path | GKE path | Cloud path | Status |
|---------|------|------------|----------|------------|--------|
| Storage | `STORAGE_BACKEND` | `local` — filesystem `/data` | `supabase` | `supabase` | Config only |
| Auth | `AUTH_PROVIDER` | None — `SUPABASE_JWT_SECRET` unset, open | `supabase` — GoTrue, HS256 | `firebase` — RS256 / JWKS | **Seam not built** |
| Queue | separate entrypoints | **None** — gateway POSTs straight to `api:8080/api/v1/ingest` | `receiver/gke_app.py` — NATS, durable pull | `receiver/main.py` — Pub/Sub push | **Already separate** |
| Inference | `config/ai.<path>.env` | `ollama-small/medium/large` containers | In-cluster Ollama, `OLLAMA_TIER=true` | Ollama Cloud, `OLLAMA_TIER=false` | **Split not done** |
| Postgres | `SUPABASE_URL` / `POSTGRES_URL` | `pgvector/pgvector:pg16` container, direct — no Kong/PostgREST | In-cluster Kong → PostgREST → StatefulSet | Cloud Run Kong → PostgREST → Cloud SQL | Config only |
| Cache | `REDIS_URL` | `redis:7-alpine` container | In-cluster Redis | Memorystore | Config only |
| Integrations | `NANGO_API_URL` | Not run | Self-hosted, `nango` namespace | Nango Cloud | Config only |
| Graph | `is_graphiti_enabled()` | `neo4j` container | In-cluster Neo4j | Off; AuraDB if it returns | Config only |
| Secrets | deploy-time | Compose env / `.env` | Kubernetes Secrets | Secret Manager | Deploy path |
| openclaw / DigiMe | `NEXT_PUBLIC_ENABLE_OPENCLAW` | Not run | Enabled | Cut | Flag not built |
| Warm floor | platform-native | n/a | KEDA `minReplicaCount` | `--min-instances` | Both at zero today |

Two local values are worth reading twice. **Auth is open** — no JWT secret is set, so local runs
unauthenticated; never treat it as evidence that an auth change is safe. And **there is no queue
locally** — the gateway posts directly to the API, so the local path exercises neither receiver
and cannot catch envelope drift. Both gaps are deliberate, but they bound what a green
`docker compose` run proves.

### Seams that must be built

Three rows above are not yet seams — they are single implementations that a naive prod migration
would overwrite. Each is Phase 0 work, and each is **additive**:

**`AUTH_PROVIDER`** — `api/main.py` verifies tokens at two sites (L263–278, L296–311), both
hardcoding `algorithms=["HS256"]` against `SUPABASE_JWT_SECRET`. No RS256 or JWKS code exists
anywhere in the API. Add a provider-selected verifier that keeps the HS256 path intact and adds
an RS256/JWKS path with key caching. `ensure_jwt_user_profile()` (`api/app/auth.py:32`)
normalizes the differing claim shapes. During transition, accept both and prefer RS256.

**`config/ai.<path>.env`** — one shared `config/ai.env` today, pinning
`OLLAMA_LOCAL_API_BASE` to the in-cluster address. Split into a shared base plus per-path
overlays so `OLLAMA_TIER` and the Ollama endpoint can differ. Note `OLLAMA_TIER` is not in
`ai.env` at all — it defaults from `config.py`, which is what makes the Cloud-path trap
invisible.

**`NEXT_PUBLIC_ENABLE_OPENCLAW`** — follows the existing `NEXT_PUBLIC_READ_ONLY` pattern.
Low urgency: `OpenClawChat.tsx` and `OpenClawExplorer.tsx` are not imported anywhere in
`ui/src` today, so the Cloud path already excludes them by default.

---

## Invariants — must never diverge

| Invariant | Why |
|-----------|-----|
| **SQL migrations** — all 15 files in `api/supabase/` | Both estates run the same schema. A path that applies a subset gets silent runtime failures, not migration errors. |
| **UniversalEnvelope contract** | The two receivers publish and consume the same payload shape. Drift here breaks the agents on one path only. |
| **Agent invocation logic** | `gke_app.py` deliberately does not import `main.py` (dependency isolation from `functions_framework` / `google-cloud-pubsub`). Shared handling belongs in a third module both import — not copied into each. |
| **Storage abstraction** (`api/app/blob_store.py`, `storage.py`) | Backend is already config-selected. Keep it that way. |
| **Secret rotation** | The committed secrets are in git history. Rotation is required for both paths, independent of platform. |

### Fixes that are not divergences

Some items read as prod work but are strict improvements to both paths. Apply them once, to
shared code, with no seam:

- **Gmail watch persistence** — `api/app/routers/gmail_push.py` defines `_WATCH_BLOB_KEY` (L37)
  but `_load_watches`/`_save_watches` use `/data/gmail_watches.json` exclusively. Routing both
  through the blob store is mandatory on Cloud Run (no disk) and removes a PVC dependency on
  GKE. Requires a one-time migration of existing watch state off the API PVC, or live Gmail
  watches drop on deploy.
- **Pinned image tags** — several manifests ride `:latest`.
- **Warm floors** — every `k8s/autoscaling/*.yaml` sits at `minReplicaCount: 0`.

---

## Change checklist

Before merging a change that touches deployment surface:

- [ ] Does it delete a manifest or asset the other path uses? → Gate behind the deploy path instead.
- [ ] Does it replace a shared implementation? → Add it alongside, selected by seam.
- [ ] Does it edit `config/ai.env` or another shared config? → Confirm the effect on both estates.
- [ ] Does it add a SQL migration? → It applies to both. No exceptions.
- [ ] Does it change envelope shape or agent invocation? → Update both receivers together.
- [ ] Does it add a host port to `docker-compose.yml`? → Parameterize it (`${FOO_PORT:-1234}`).
- [ ] Does it pin a dependency? → Bound the major version. An unbounded `>=` broke `mcp-server`
      when `mcp` 2.x renamed `FastMCP`.

## Verified state — local path

Brought up on 2026-08-26 with `docker compose`, all eight non-Ollama services healthy: `ui`
(3000), `api` (8080), `webhook-gateway` (8070), `mcp-server` (8091), `webhook-processor` (8090),
`neo4j` (7474), `db`, `redis`. Ingest verified end to end — `POST /api/v1/data` (multipart)
returned a `data_id`, and `GET /api/v1/data/{id}` returned 200.

The three `ollama-*` tiers were **not** started; they pull roughly 20 GB of model weights. Use
[`docker-compose.lean.yml`](../../docker-compose.lean.yml), which skips them and sets
`OLLAMA_TIER=false`, unless you specifically need local inference.
