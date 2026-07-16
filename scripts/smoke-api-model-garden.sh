#!/usr/bin/env bash
# =============================================================================
# Smoke script: API health + AI / model config probes
# =============================================================================
# Always checks:
#   GET  /health
#   POST /api/v1/ai/query/test
#   GET  /api/v1/ai/model-catalog
#
# Optional lean/local host Ollama (when OLLAMA_URL is reachable, default
# http://127.0.0.1:11434):
#   GET  {OLLAMA_URL}/api/tags
#
# Optional GKE/machine garden paths (skipped unless SMOKE_GKE_MODELS=1):
#   GET  /api/v1/models/machines
#
# Usage:
#   API_URL=http://localhost:8080 ./scripts/smoke-api-model-garden.sh
#   ./scripts/smoke-api-model-garden.sh http://localhost:8080
#
# Auth (lean API_KEY or Cloud Run identity token):
#   API_KEY=dev-local-key ./scripts/smoke-api-model-garden.sh http://localhost:8080
#   AUTH_HEADER="Authorization: Bearer $(gcloud auth print-identity-token)" ./scripts/...
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

API_KEY="${API_KEY:-${MEM_DOG_API_KEY:-}}"
AUTH_HEADER="${AUTH_HEADER:-}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
SMOKE_GKE_MODELS="${SMOKE_GKE_MODELS:-0}"

CURL_EXTRA=()
if [ -n "$AUTH_HEADER" ]; then
  CURL_EXTRA+=(-H "$AUTH_HEADER")
fi
if [ -n "$API_KEY" ]; then
  CURL_EXTRA+=(-H "x-api-key: ${API_KEY}")
fi

check() {
  local method="$1"
  local path="$2"
  local code
  code=$(curl -s -o /tmp/smoke_mg_body -w '%{http_code}' -X "$method" \
    ${CURL_EXTRA[@]+"${CURL_EXTRA[@]}"} --max-time 30 "$API_URL$path" 2>/dev/null || echo "000")
  if [ "$code" = "200" ] || [ "$code" = "201" ] || [ "$code" = "204" ]; then
    echo "  OK  $method $path → $code"
    return 0
  fi
  echo "  FAIL $method $path → $code"
  return 1
}

check_external() {
  local label="$1"
  local url="$2"
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$url" 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    echo "  OK  $label → $code"
    return 0
  fi
  echo "  SKIP $label → $code (optional)"
  return 0
}

FAILED=0

echo "Smoke check: $API_URL"
[ -n "$API_KEY" ] && echo "Auth: x-api-key set" || echo "Auth: none (set API_KEY if API requires it)"
echo ""

if ! check GET "/health"; then FAILED=1; fi
if ! check POST "/api/v1/ai/query/test"; then FAILED=1; fi
if ! check GET "/api/v1/ai/model-catalog"; then FAILED=1; fi

# Host Ollama used by lean k8s / compose lean
check_external "host Ollama ${OLLAMA_URL}/api/tags" "${OLLAMA_URL}/api/tags"

if [ "$SMOKE_GKE_MODELS" = "1" ]; then
  if ! check GET "/api/v1/models/machines"; then FAILED=1; fi
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "All required checks passed."
  exit 0
else
  echo "One or more required checks failed."
  exit 1
fi
