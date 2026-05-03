#!/usr/bin/env bash
# =============================================================================
# Smoke script: API health + model garden endpoints
# =============================================================================
# Calls GET /health, GET /api/v1/models/storage-status, and
# GET /api/v1/ai/query/model-server/health?tier=medium. Exits 0 if all return 2xx.
# Use after deploying API (and optionally model servers) to verify model garden.
#
# Usage:
#   API_URL=https://memdog-api-xxx.run.app ./scripts/smoke-api-model-garden.sh
#   ./scripts/smoke-api-model-garden.sh https://memdog-api-xxx.run.app
#
# Optional auth (e.g. Cloud Run with --no-allow-unauthenticated):
#   ID_TOKEN=$(gcloud auth print-identity-token)
#   API_URL=... AUTH_HEADER="Authorization: Bearer $ID_TOKEN" ./scripts/smoke-api-model-garden.sh
# =============================================================================

set -euo pipefail

API_URL="${API_URL:-}"
if [ -n "${1:-}" ]; then
  API_URL="$1"
fi
if [ -z "$API_URL" ]; then
  echo "Usage: API_URL=<url> $0  OR  $0 <api_url>"
  exit 1
fi
API_URL="${API_URL%/}"

AUTH_HEADER="${AUTH_HEADER:-}"
CURL_EXTRA=()
if [ -n "$AUTH_HEADER" ]; then
  CURL_EXTRA+=(-H "$AUTH_HEADER")
fi

check() {
  local path="$1"
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' "${CURL_EXTRA[@]}" --max-time 30 "$API_URL$path" 2>/dev/null || echo "000")
  if [ "$code" = "200" ] || [ "$code" = "204" ]; then
    echo "  OK $path → $code"
    return 0
  fi
  echo "  FAIL $path → $code"
  return 1
}

FAILED=0

echo "Smoke check: $API_URL"
echo ""

if ! check "/health"; then FAILED=1; fi
if ! check "/api/v1/models/storage-status"; then FAILED=1; fi
if ! check "/api/v1/ai/query/model-server/health?tier=medium"; then FAILED=1; fi

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "All checks passed."
  exit 0
else
  echo "One or more checks failed."
  exit 1
fi
