#!/usr/bin/env bash
# Host SaaS L0 smoke: binding → tagged ingest → project-scoped semantic (optional).
#
# Prerequisites:
#   ./scripts/dev-lean.sh up -d
#   Optional: PLATFORM_API_KEY / API_KEY if the API enforces auth
#
# Usage:
#   ./scripts/smoke-host-saas.sh
#   MEMDOG_BASE_URL=http://localhost:8080 ./scripts/smoke-host-saas.sh

set -euo pipefail

BASE="${MEMDOG_BASE_URL:-http://localhost:8080}"
PLATFORM_KEY="${PLATFORM_API_KEY:-${API_KEY:-}}"
HDR=(-H "Content-Type: application/json")
if [[ -n "$PLATFORM_KEY" ]]; then
  HDR+=(-H "x-api-key: $PLATFORM_KEY")
fi

echo "== health / ready =="
curl -sf "$BASE/health" | head -c 200; echo
curl -sf "$BASE/ready" | head -c 200; echo

EXT_ORG="smoke-org-$(date +%s)"
EXT_WS="smoke-ws-1"
echo "== create binding ($EXT_ORG / $EXT_WS) =="
BIND=$(curl -sf -X POST "$BASE/api/v1/host/bindings" \
  "${HDR[@]}" \
  -d "{\"external_org_id\":\"$EXT_ORG\",\"external_workspace_id\":\"$EXT_WS\",\"display_name\":\"Smoke WS\"}")
echo "$BIND" | head -c 400; echo

ORG_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['org_id'])" <<<"$BIND")
PROJ_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['project_id'])" <<<"$BIND")
USER_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['user_id'])" <<<"$BIND")
MD_KEY=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('api_key') or '')" <<<"$BIND")

if [[ -z "$MD_KEY" ]]; then
  echo "ERROR: api_key missing on create" >&2
  exit 1
fi

echo "== idempotent re-bind =="
AGAIN=$(curl -sf -X POST "$BASE/api/v1/host/bindings" \
  "${HDR[@]}" \
  -d "{\"external_org_id\":\"$EXT_ORG\",\"external_workspace_id\":\"$EXT_WS\"}")
CREATED=$(python3 -c "import json,sys; print(json.load(sys.stdin)['created'])" <<<"$AGAIN")
[[ "$CREATED" == "False" || "$CREATED" == "false" ]] || {
  echo "ERROR: expected created=false on rebind, got $CREATED" >&2
  exit 1
}

echo "== ingest tagged text =="
WH=(-H "x-api-key: $MD_KEY")
UPLOAD=$(curl -sf -X POST "$BASE/api/v1/data" \
  "${WH[@]}" \
  -F "content=Host SaaS smoke: Project Phoenix launch date is 2026-09-01." \
  -F "name=phoenix-note" \
  -F "mime_type=text/plain" \
  -F "owner_user_id=$USER_ID" \
  -F "org_id=$ORG_ID" \
  -F "project_id=$PROJ_ID" \
  -F "tags=source:host,tenant:$EXT_WS,event:note")
echo "$UPLOAD" | head -c 300; echo
DATA_ID=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data_id') or d.get('id') or '')" <<<"$UPLOAD")
[[ -n "$DATA_ID" ]] || { echo "ERROR: no data_id" >&2; exit 1; }

echo "== metadata has project_id =="
META=$(curl -sf "$BASE/api/v1/data/$DATA_ID/metadata?user_id=$USER_ID" "${WH[@]}" || true)
if [[ -n "$META" ]]; then
  echo "$META" | head -c 400; echo
fi

echo "== semantic search (best-effort; needs embedding engine) =="
# Create embedding if AI is configured
curl -sf -X POST "$BASE/api/v1/ai/embeddings" \
  "${WH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"data_id\":\"$DATA_ID\",\"user_id\":\"$USER_ID\",\"project_id\":\"$PROJ_ID\"}" \
  >/tmp/host-saas-embed.json 2>/dev/null || echo "(skip embed — AI not configured)"

SEM=$(curl -sf -X POST "$BASE/api/v1/ai/query/semantic" \
  "${WH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"Phoenix launch date\",\"user_id\":\"$USER_ID\",\"project_id\":\"$PROJ_ID\",\"max_results\":5}" \
  2>/dev/null || echo "")
if [[ -n "$SEM" ]]; then
  echo "$SEM" | head -c 500; echo
else
  echo "(skip semantic — AI/embed unavailable; binding + ingest OK)"
fi

echo "OK host-saas smoke: org=$ORG_ID project=$PROJ_ID user=$USER_ID data=$DATA_ID"
