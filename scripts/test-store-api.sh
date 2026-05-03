#!/usr/bin/env bash
# =============================================================================
# Mem-Dog Store API Test Script
# =============================================================================
# Runs insert/select/delete tests against the mem-dog store API for a given
# backend (supabase, redis, postgres, gcs). Mirrors the store_kv table
# test in create_supabase_store_kv.
#
# Prerequisites:
#   - A running mem-dog API with the chosen store backend configured
#   - curl
#
# Usage:
#   ./scripts/test-store-api.sh [--url URL] [--backend supabase]
#
# Options:
#   -u, --url      API base URL (default: http://localhost:8080)
#   -b, --backend  Store backend: supabase|redis|postgres|gcs (default: supabase)
#   -a, --auth     Use gcloud identity token for Cloud Run auth
#   -v, --verbose  Print full response bodies
#   -r, --retries  Retry 5xx/connection errors N times (default: 3)
#   -h, --help     Show this help
#
# Examples:
#   ./scripts/test-store-api.sh
#   ./scripts/test-store-api.sh --url https://mem-dog-api-xxx.run.app --auth
#   ./scripts/test-store-api.sh --url http://localhost:8080 --backend redis
# =============================================================================

set -euo pipefail

API_URL="http://localhost:8080"
BACKEND="supabase"
USE_AUTH=false
VERBOSE=false
RETRIES=3

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

pass() { echo -e "${GREEN}  ✓ PASS${NC} $1"; }
fail() { echo -e "${RED}  ✗ FAIL${NC} $1"; }
info() { echo -e "${BLUE}  ↳${NC} $1"; }

# Print remediation steps when something fails
howto() {
  echo ""
  echo -e "${YELLOW}To fix / How to succeed:${NC}"
  while [[ $# -gt 0 ]]; do
    echo -e "  ${YELLOW}•${NC} $1"
    shift
  done
  echo ""
}

while [[ $# -gt 0 ]]; do
  case $1 in
    -u|--url)     API_URL="$2"; shift 2;;
    -b|--backend) BACKEND="$2"; shift 2;;
    -a|--auth)    USE_AUTH=true; shift;;
    -v|--verbose) VERBOSE=true; shift;;
    -r|--retries) RETRIES="$2"; shift 2;;
    -h|--help)    head -30 "$0" | tail -25; exit 0;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

API_URL="${API_URL%/}"
TEST_KEY="kv_store_$(date +%s)_${RANDOM:-$$}"
TEST_VALUE="test"
STORE_PARAM=""
case "$BACKEND" in
  supabase) STORE_PARAM="supabase=true";;
  redis)    STORE_PARAM="redis=true";;
  postgres) STORE_PARAM="postgres=true";;
  gcs)      STORE_PARAM="gcs=true";;
  *) echo "Unknown backend: $BACKEND"; exit 1;;
esac

CURL_EXTRA=()
if $USE_AUTH; then
  TOKEN=$(gcloud auth print-identity-token 2>/dev/null || true)
  if [ -z "$TOKEN" ]; then
    echo "Error: --auth requires gcloud auth. Run: gcloud auth login"
    exit 1
  fi
  CURL_EXTRA+=(-H "Authorization: Bearer $TOKEN")
fi

do_curl() {
  local method="$1" path="$2"; shift 2
  local url="${API_URL}${path}"
  local tmp; tmp=$(mktemp)
  local http_code
  http_code=$(curl -s -o "$tmp" -w "%{http_code}" -X "$method" "$url" "${CURL_EXTRA[@]}" "$@" 2>/dev/null || echo "000")
  local body; body=$(cat "$tmp"); rm -f "$tmp"
  if $VERBOSE; then
    echo -e "    ${BLUE}${method} ${path} → ${http_code}${NC}" >&2
    echo "$body" >&2
  fi
  echo "${http_code}|||${body}"
}

# Retry on 5xx or 000 (connection error). Returns last result.
do_curl_retry() {
  local attempt=1
  local r
  r=$(do_curl "$@")
  local code; code=$(http_code "$r")
  while [[ $attempt -lt $RETRIES ]] && { [[ "$code" == "000" ]] || [[ "$code" =~ ^5[0-9][0-9]$ ]]; }; do
    info "  Retry $attempt/$RETRIES (HTTP $code) in 2s..."
    sleep 2
    attempt=$((attempt + 1))
    r=$(do_curl "$@")
    code=$(http_code "$r")
  done
  echo "$r"
}

http_code() { echo "$1" | cut -d'|' -f1; }
body()      { echo "$1" | cut -d'|' -f4-; }

assert_status() {
  local result="$1" expected="$2" label="$3"
  local code; code=$(http_code "$result")
  if [[ "$code" == "$expected" ]]; then
    pass "$label (HTTP $code)"
    return 0
  else
    fail "$label (expected HTTP $expected, got $code)"
    local b; b=$(body "$result")
    [[ -n "$b" ]] && echo "    $b"
    return 1
  fi
}

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║         Mem-Dog Store API Test               ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
info "API URL  : ${API_URL}"
info "Backend  : ${BACKEND}"
info "Test key : ${TEST_KEY}"
info "Retries  : ${RETRIES} (on 5xx/connection errors)"
echo ""

FAILED=0

# 0. Check if store backend exists (configured and reachable)
info "Step 0: Checking if store backend '${BACKEND}' is configured..."
info "  Running: curl -s -o /dev/null -w '%{http_code}' ${API_URL}/api/v1/store?${STORE_PARAM}"
r=$(do_curl GET "/api/v1/store?${STORE_PARAM}")
CODE=$(http_code "$r")
if [[ "$CODE" == "503" ]]; then
  fail "Store backend '${BACKEND}' not configured (HTTP 503)"
  case "$BACKEND" in
    supabase)
      howto \
        "Set SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) in the API env" \
        "Deploy API with: USE_SUPABASE_STORAGE=true ./scripts/manual-deploy.sh deploy-api -p PROJECT -e dev" \
        "For GCP: run setup-supabase then deploy-api with USE_SUPABASE_STORAGE=true"
      ;;
    redis)
      howto \
        "Set REDIS_URL in the API env (e.g. redis://localhost:6379/0)" \
        "Deploy with: USE_REDIS_STORAGE=true ./scripts/manual-deploy.sh deploy-api -p PROJECT -e dev"
      ;;
    postgres)
      howto \
        "Set POSTGRES_URL in the API env" \
        "Deploy with: USE_POSTGRES_STORAGE=true ./scripts/manual-deploy.sh deploy-api -p PROJECT -e dev"
      ;;
    gcs)
      howto \
        "Set STORE_GCS_BUCKET in the API env" \
        "Deploy with STORE_GCS_BUCKET set (e.g. create a bucket and pass it when deploying the API)"
      ;;
    *) howto "Configure the ${BACKEND} store backend in the API environment" ;;
  esac
  exit 1
elif [[ "$CODE" != "200" ]]; then
  fail "Store check failed (expected 200, got $CODE)"
  [[ -n "$(body "$r")" ]] && echo "    Response: $(body "$r")"
  howto \
    "Verify API is running: curl ${API_URL}/health" \
    "If Cloud Run: use --auth to pass gcloud identity token" \
    "Check API logs for connection errors"
  exit 1
fi
pass "Store backend '${BACKEND}' available (GET /api/v1/store)"

# 1. Insert (PUT)
info "Step 1: Inserting test value..."
info "  Running: curl -X PUT ${API_URL}/api/v1/store/${TEST_KEY}?${STORE_PARAM} -d '${TEST_VALUE}'"
r=$(do_curl_retry PUT "/api/v1/store/${TEST_KEY}?${STORE_PARAM}" \
  -H "Content-Type: text/plain" \
  -d "$TEST_VALUE")
assert_status "$r" "200" "PUT /api/v1/store/{key} (insert)" || FAILED=1

# 2. Read (GET)
info "Step 2: Reading back the value..."
r=$(do_curl_retry GET "/api/v1/store/${TEST_KEY}?${STORE_PARAM}")
if ! assert_status "$r" "200" "GET /api/v1/store/{key} (read)"; then
  FAILED=1
else
  GOT=$(body "$r")
  if [[ "$GOT" == "$TEST_VALUE" ]]; then
    pass "  Value round-trips correctly"
  else
    fail "  Value mismatch: expected '$TEST_VALUE', got '$GOT'"
    FAILED=1
  fi
fi

# 3. List keys (optional check)
info "Step 3: Listing keys..."
r=$(do_curl GET "/api/v1/store?${STORE_PARAM}")
CODE=$(http_code "$r")
if [[ "$CODE" == "200" ]]; then
  if body "$r" | grep -q "$TEST_KEY"; then
    pass "GET /api/v1/store (list) — key present"
  else
    pass "GET /api/v1/store (list) — HTTP 200"
  fi
else
  fail "GET /api/v1/store (list) — HTTP $CODE"
  FAILED=1
fi

# 4. Delete (DELETE)
info "Step 4: Deleting the test key..."
r=$(do_curl_retry DELETE "/api/v1/store/${TEST_KEY}?${STORE_PARAM}")
assert_status "$r" "204" "DELETE /api/v1/store/{key} (delete)" || FAILED=1

# 5. Verify 404 after delete
info "Step 5: Verifying 404 after delete..."
r=$(do_curl GET "/api/v1/store/${TEST_KEY}?${STORE_PARAM}")
assert_status "$r" "404" "GET after delete returns 404" || FAILED=1

echo ""
if [[ $FAILED -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}  All store API tests passed (${BACKEND})${NC}"
  echo ""
  exit 0
else
  echo -e "${RED}${BOLD}  One or more tests failed.${NC}"
  howto \
    "Run with --verbose to see full request/response: $0 --url $API_URL --backend $BACKEND ${USE_AUTH:+--auth} --verbose" \
    "Supabase 401: check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY" \
    "PGRST205 (table not in schema cache): apply migrations in Supabase (api/supabase/*.sql) and reload schema in Supabase dashboard" \
    "Verify the store backend is healthy (e.g. Supabase: check PostgREST and tables)" \
    "Check API logs: gcloud run services logs read mem-dog-api --region us-central1 --limit 50"
  exit 1
fi
