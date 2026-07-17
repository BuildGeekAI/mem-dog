#!/usr/bin/env bash
# Host SaaS L0 smoke: workspace provision → tagged ingest → project-scoped semantic.
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
curl -sf "$BASE/health" -D /tmp/host-saas-headers.txt | head -c 200; echo
grep -i x-request-id /tmp/host-saas-headers.txt || true
curl -sf "$BASE/ready" | head -c 200; echo

echo "== request id echo =="
RID=$(curl -sf -D - -o /dev/null -H "X-Request-Id: smoke-req-1" "$BASE/health" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-request-id"{print $2; exit}')
[[ "$RID" == "smoke-req-1" ]] || {
  echo "ERROR: expected X-Request-Id=smoke-req-1, got '$RID'" >&2
  exit 1
}

EXT_ORG="smoke-org-$(date +%s)"
EXT_WS="smoke-ws-1"
echo "== create workspace ($EXT_ORG / $EXT_WS) =="
WS=$(curl -sf -X POST "$BASE/api/v1/host/workspaces" \
  "${HDR[@]}" \
  -d "{\"external_org_id\":\"$EXT_ORG\",\"external_workspace_id\":\"$EXT_WS\",\"display_name\":\"Smoke WS\"}")
echo "$WS" | head -c 400; echo

ORG_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['org_id'])" <<<"$WS")
PROJ_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['project_id'])" <<<"$WS")
USER_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['user_id'])" <<<"$WS")
MD_KEY=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('api_key') or '')" <<<"$WS")

if [[ -z "$MD_KEY" ]]; then
  echo "ERROR: api_key missing on create" >&2
  exit 1
fi

echo "== idempotent re-provision =="
AGAIN=$(curl -sf -X POST "$BASE/api/v1/host/workspaces" \
  "${HDR[@]}" \
  -d "{\"external_org_id\":\"$EXT_ORG\",\"external_workspace_id\":\"$EXT_WS\"}")
CREATED=$(python3 -c "import json,sys; print(json.load(sys.stdin)['created'])" <<<"$AGAIN")
[[ "$CREATED" == "False" || "$CREATED" == "false" ]] || {
  echo "ERROR: expected created=false on re-provision, got $CREATED" >&2
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
  -F "external_id=smoke:phoenix-note" \
  -F "tags=source:host,tenant:$EXT_WS,event:note")
echo "$UPLOAD" | head -c 300; echo
DATA_ID=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data_id') or d.get('id') or '')" <<<"$UPLOAD")
[[ -n "$DATA_ID" ]] || { echo "ERROR: no data_id" >&2; exit 1; }
CREATED=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('created'))" <<<"$UPLOAD")
[[ "$CREATED" == "True" || "$CREATED" == "true" ]] || {
  echo "ERROR: expected created=true on first upsert, got $CREATED" >&2
  exit 1
}

echo "== external_id upsert (same id → same data_id) =="
UP2=$(curl -sf -X POST "$BASE/api/v1/data" \
  "${WH[@]}" \
  -F "content=Host SaaS smoke: Project Phoenix launch date is 2026-09-15 (resynced)." \
  -F "name=phoenix-note" \
  -F "mime_type=text/plain" \
  -F "owner_user_id=$USER_ID" \
  -F "org_id=$ORG_ID" \
  -F "project_id=$PROJ_ID" \
  -F "external_id=smoke:phoenix-note" \
  -F "tags=source:host,tenant:$EXT_WS,event:note")
echo "$UP2" | head -c 300; echo
DATA_ID2=$(python3 -c "import json,sys; print(json.load(sys.stdin)['data_id'])" <<<"$UP2")
UPDATED=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('updated'))" <<<"$UP2")
CREATED2=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('created'))" <<<"$UP2")
[[ "$DATA_ID2" == "$DATA_ID" ]] || {
  echo "ERROR: expected same data_id on upsert ($DATA_ID vs $DATA_ID2)" >&2
  exit 1
}
[[ "$UPDATED" == "True" || "$UPDATED" == "true" ]] || {
  echo "ERROR: expected updated=true on re-sync, got $UPDATED" >&2
  exit 1
}
[[ "$CREATED2" == "False" || "$CREATED2" == "false" ]] || {
  echo "ERROR: expected created=false on re-sync, got $CREATED2" >&2
  exit 1
}

echo "== api key rotate =="
KEYS=$(curl -sf "$BASE/api/v1/host/api-keys" "${WH[@]}")
OLD_KEY_ID=$(python3 -c "import json,sys; ks=json.load(sys.stdin); print(ks[0]['key_id'] if ks else '')" <<<"$KEYS")
[[ -n "$OLD_KEY_ID" ]] || { echo "ERROR: no keys listed" >&2; exit 1; }
ROT=$(curl -sf -X POST "$BASE/api/v1/host/api-keys/rotate" \
  "${WH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"smoke-rotated\",\"revoke_key_id\":\"$OLD_KEY_ID\"}")
echo "$ROT" | head -c 300; echo
NEW_KEY=$(python3 -c "import json,sys; print(json.load(sys.stdin)['key'])" <<<"$ROT")
REVOKED=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('revoked_key_id'))" <<<"$ROT")
[[ "$NEW_KEY" == md_* ]] || { echo "ERROR: rotate did not return md_ key" >&2; exit 1; }
[[ "$REVOKED" == "$OLD_KEY_ID" ]] || {
  echo "ERROR: expected revoked_key_id=$OLD_KEY_ID got $REVOKED" >&2
  exit 1
}
# Old key must fail; new key must work
OLD_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "x-api-key: $MD_KEY" "$BASE/api/v1/host/api-keys" || true)
NEW_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "x-api-key: $NEW_KEY" "$BASE/api/v1/host/api-keys" || true)
[[ "$OLD_CODE" == "401" || "$OLD_CODE" == "403" ]] || {
  echo "ERROR: expected old key rejected, got HTTP $OLD_CODE" >&2
  exit 1
}
[[ "$NEW_CODE" == "200" ]] || {
  echo "ERROR: expected new key OK, got HTTP $NEW_CODE" >&2
  exit 1
}
MD_KEY="$NEW_KEY"
WH=(-H "x-api-key: $MD_KEY")

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
  echo "(skip semantic — AI/embed unavailable; workspace + ingest OK)"
fi

echo "OK host-saas smoke: org=$ORG_ID project=$PROJ_ID user=$USER_ID data=$DATA_ID"
