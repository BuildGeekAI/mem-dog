#!/usr/bin/env bash
# =============================================================================
# Mem-Dog End-to-End API Test Script
# =============================================================================
# Runs a full suite of curl tests against a live mem-dog API:
#   - Health check
#   - Data CRUD (JSON, text, file upload)
#   - Metadata, info (name/description), tags, access control
#   - Versioning (historical version reads)
#   - Memories (create, associate, list, delete)
#   - Bulk delete
#   - Cleanup of all test data
#
# Prerequisites:
#   - A running mem-dog API (local or Cloud Run)
#   - curl, python3
#
# Usage:
#   ./scripts/test-api.sh [--url http://localhost:8080] [--api-key KEY]
#
# Options:
#   -u, --url      API base URL  (default: http://localhost:8080)
#   -k, --api-key  x-api-key header (also: API_KEY / MEM_DOG_API_KEY env)
#   -v, --verbose  Print full response bodies
#   -h, --help     Show this help
#
# Examples:
#   ./scripts/test-api.sh
#   ./scripts/test-api.sh --url http://localhost:8080 --api-key dev-local-key
#   API_KEY=dev-local-key ./scripts/test-api.sh --url http://localhost:8080 --verbose
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
API_URL="http://localhost:8080"
API_KEY="${API_KEY:-${MEM_DOG_API_KEY:-}}"
VERBOSE=false
# Must match api DEFAULT_USER_ID — memory GET/PUT require ?user_id=
TEST_USER_ID="00000000-0000-0000-0000-000000000001"

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS=0
FAIL=0
SKIP=0

pass() { echo -e "${GREEN}  ✓ PASS${NC} $1"; (( PASS++ )) || true; }
fail() { echo -e "${RED}  ✗ FAIL${NC} $1"; (( FAIL++ )) || true; }
skip() { echo -e "${YELLOW}  - SKIP${NC} $1"; (( SKIP++ )) || true; }
section() { echo ""; echo -e "${BOLD}${CYAN}── $1 ──────────────────────────────────────${NC}"; }
info()    { echo -e "${BLUE}  ↳${NC} $1"; }

# Extract a JSON field value (requires python3)
json_get() {
  local json="$1" field="$2"
  echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$field',''))" 2>/dev/null || true
}

# Run a curl call, capture HTTP status + body
# Usage: do_curl <method> <path> [extra curl args...]
do_curl() {
  local method="$1" path="$2"; shift 2
  local url="${API_URL}${path}"
  local tmp; tmp=$(mktemp)
  local http_code
  local auth_args=()
  if [[ -n "$API_KEY" ]]; then
    auth_args=(-H "x-api-key: ${API_KEY}")
  fi
  http_code=$(curl -s -o "$tmp" -w "%{http_code}" -X "$method" "$url" "${auth_args[@]}" "$@" 2>/dev/null || echo "000")
  local body; body=$(cat "$tmp"); rm -f "$tmp"
  if $VERBOSE; then
    echo -e "    ${BLUE}${method} ${path} → ${http_code}${NC}"
    echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
  fi
  echo "${http_code}|||${body}"
}

# Split the result from do_curl
http_code() { echo "$1" | cut -d'|' -f1; }
body()      { echo "$1" | cut -d'|' -f4-; }

# Assert HTTP status code
assert_status() {
  local result="$1" expected="$2" label="$3"
  local code; code=$(http_code "$result")
  if [[ "$code" == "$expected" ]]; then
    pass "$label (HTTP $code)"
  else
    fail "$label (expected HTTP $expected, got $code)"
    local b; b=$(body "$result")
    [[ -n "$b" ]] && echo "    $b"
  fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    -u|--url)     API_URL="$2"; shift 2;;
    -k|--api-key) API_KEY="$2"; shift 2;;
    -v|--verbose) VERBOSE=true; shift;;
    -h|--help)    head -35 "$0" | tail -30; exit 0;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

# Strip trailing slash
API_URL="${API_URL%/}"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║      Mem-Dog API End-to-End Test Suite       ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
info "API URL : ${API_URL}"
if [[ -n "$API_KEY" ]]; then
  info "API key : set"
else
  info "API key : not set"
fi
info "Verbose : ${VERBOSE}"
echo ""

# Keep track of created IDs for cleanup
CREATED_DATA_IDS=()
CREATED_MEMORY_IDS=()
CREATED_VIEWPOINT_IDS=()
CREATED_PROMPT_IDS=()

# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------
section "1. Health Check"

r=$(do_curl GET "/")
assert_status "$r" "200" "GET / returns 200"

# ---------------------------------------------------------------------------
# 2. Data — JSON content
# ---------------------------------------------------------------------------
section "2. Create Data (JSON)"

r=$(do_curl POST "/api/v1/data" \
  -F 'content={"test": "hello", "value": 42}' \
  -F 'name=test_json_item' \
  -F 'description=Created by test-api.sh' \
  -F 'tags=test,automated')
assert_status "$r" "200" "POST /api/v1/data (JSON content)"

DATA_ID_JSON=$(json_get "$(body "$r")" "data_id")
if [[ -n "$DATA_ID_JSON" ]]; then
  info "data_id = $DATA_ID_JSON"
  CREATED_DATA_IDS+=("$DATA_ID_JSON")
else
  fail "No data_id returned from JSON create"
fi

# ---------------------------------------------------------------------------
# 3. Data — plain text
# ---------------------------------------------------------------------------
section "3. Create Data (plain text)"

r=$(do_curl POST "/api/v1/data" \
  -F 'content=Hello from test-api.sh' \
  -F 'name=test_text_item')
assert_status "$r" "200" "POST /api/v1/data (text content)"

DATA_ID_TEXT=$(json_get "$(body "$r")" "data_id")
[[ -n "$DATA_ID_TEXT" ]] && { info "data_id = $DATA_ID_TEXT"; CREATED_DATA_IDS+=("$DATA_ID_TEXT"); }

# ---------------------------------------------------------------------------
# 4. Data — file upload (create a temp file)
# ---------------------------------------------------------------------------
section "4. Create Data (file upload)"

TMP_FILE=$(mktemp /tmp/memdog-test-XXXXXX.txt)
echo "This is a test file created by test-api.sh at $(date -u)" > "$TMP_FILE"

r=$(do_curl POST "/api/v1/data" \
  -F "file=@${TMP_FILE}" \
  -F 'name=test_file_upload')
assert_status "$r" "200" "POST /api/v1/data (file upload)"

DATA_ID_FILE=$(json_get "$(body "$r")" "data_id")
[[ -n "$DATA_ID_FILE" ]] && { info "data_id = $DATA_ID_FILE"; CREATED_DATA_IDS+=("$DATA_ID_FILE"); }
rm -f "$TMP_FILE"

# ---------------------------------------------------------------------------
# 5. List data
# ---------------------------------------------------------------------------
section "5. List Data"

r=$(do_curl GET "/api/v1/data?limit=10")
assert_status "$r" "200" "GET /api/v1/data"

TOTAL=$(json_get "$(body "$r")" "total")
info "total items = ${TOTAL:-unknown}"

# ---------------------------------------------------------------------------
# 6. Read data content
# ---------------------------------------------------------------------------
section "6. Read Data Content"

if [[ -n "$DATA_ID_JSON" ]]; then
  r=$(do_curl GET "/api/v1/data/${DATA_ID_JSON}")
  assert_status "$r" "200" "GET /api/v1/data/{id} (JSON)"
  CONTENT=$(body "$r")
  if echo "$CONTENT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('test')=='hello'" 2>/dev/null; then
    pass "  JSON content round-trips correctly"
  else
    fail "  JSON content mismatch: $CONTENT"
  fi
fi

if [[ -n "$DATA_ID_TEXT" ]]; then
  r=$(do_curl GET "/api/v1/data/${DATA_ID_TEXT}")
  assert_status "$r" "200" "GET /api/v1/data/{id} (text)"
fi

# ---------------------------------------------------------------------------
# 7. Get metadata
# ---------------------------------------------------------------------------
section "7. Get Metadata"

if [[ -n "$DATA_ID_JSON" ]]; then
  r=$(do_curl GET "/api/v1/data/${DATA_ID_JSON}/metadata")
  assert_status "$r" "200" "GET /api/v1/data/{id}/metadata"
  VERSION=$(json_get "$(body "$r")" "current_version")
  info "current_version = ${VERSION:-?}"
fi

# ---------------------------------------------------------------------------
# 8. Update data (creates a new version)
# ---------------------------------------------------------------------------
section "8. Update Data (versioning)"

if [[ -n "$DATA_ID_JSON" ]]; then
  r=$(do_curl PUT "/api/v1/data/${DATA_ID_JSON}" \
    -F 'content={"test": "updated", "value": 99}')
  assert_status "$r" "200" "PUT /api/v1/data/{id}"
  NEW_VERSION=$(json_get "$(body "$r")" "version")
  info "new version = ${NEW_VERSION:-?}"

  # Read historical version 1
  r=$(do_curl GET "/api/v1/data/${DATA_ID_JSON}?version=1")
  assert_status "$r" "200" "GET /api/v1/data/{id}?version=1 (historical)"
  if echo "$(body "$r")" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('value')==42" 2>/dev/null; then
    pass "  Historical v1 content is correct"
  else
    fail "  Historical v1 content mismatch"
  fi

  # Read current version
  r=$(do_curl GET "/api/v1/data/${DATA_ID_JSON}")
  if echo "$(body "$r")" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('value')==99" 2>/dev/null; then
    pass "  Current version content is updated"
  else
    fail "  Current version content mismatch after update"
  fi
fi

# ---------------------------------------------------------------------------
# 9. Info (name & description)
# ---------------------------------------------------------------------------
section "9. Name & Description (Info)"

if [[ -n "$DATA_ID_JSON" ]]; then
  r=$(do_curl GET "/api/v1/data/${DATA_ID_JSON}/info")
  assert_status "$r" "200" "GET /api/v1/data/{id}/info"
  NAME=$(json_get "$(body "$r")" "name")
  info "name = ${NAME:-null}"

  r=$(do_curl PUT "/api/v1/data/${DATA_ID_JSON}/info" \
    -H "Content-Type: application/json" \
    -d '{"name": "updated_test_name", "description": "Updated by test script"}')
  assert_status "$r" "200" "PUT /api/v1/data/{id}/info"

  r=$(do_curl GET "/api/v1/data/${DATA_ID_JSON}/info")
  UPDATED_NAME=$(json_get "$(body "$r")" "name")
  if [[ "$UPDATED_NAME" == "updated_test_name" ]]; then
    pass "  Name updated correctly"
  else
    fail "  Name update failed (got: $UPDATED_NAME)"
  fi
fi

# ---------------------------------------------------------------------------
# 10. Tags
# ---------------------------------------------------------------------------
section "10. Tags"

if [[ -n "$DATA_ID_JSON" ]]; then
  r=$(do_curl GET "/api/v1/data/${DATA_ID_JSON}/tags")
  assert_status "$r" "200" "GET /api/v1/data/{id}/tags"

  r=$(do_curl POST "/api/v1/data/${DATA_ID_JSON}/tags/add" \
    -H "Content-Type: application/json" \
    -d '{"tags": ["extra-tag", "curl-test"]}')
  assert_status "$r" "200" "POST /api/v1/data/{id}/tags/add"

  r=$(do_curl POST "/api/v1/data/${DATA_ID_JSON}/tags/remove" \
    -H "Content-Type: application/json" \
    -d '{"tags": ["extra-tag"]}')
  assert_status "$r" "200" "POST /api/v1/data/{id}/tags/remove"
fi

# ---------------------------------------------------------------------------
# 11. Access control
# ---------------------------------------------------------------------------
section "11. Access Control"

if [[ -n "$DATA_ID_JSON" ]]; then
  r=$(do_curl GET "/api/v1/data/${DATA_ID_JSON}/access")
  assert_status "$r" "200" "GET /api/v1/data/{id}/access"

  # Restrict to authenticated users
  r=$(do_curl PUT "/api/v1/data/${DATA_ID_JSON}/access" \
    -H "Content-Type: application/json" \
    -d '{"access": ["*"]}')
  assert_status "$r" "200" "PUT /api/v1/data/{id}/access (set to [\"*\"])"

  # Reset to public
  r=$(do_curl PUT "/api/v1/data/${DATA_ID_JSON}/access" \
    -H "Content-Type: application/json" \
    -d '{"access": null}')
  assert_status "$r" "200" "PUT /api/v1/data/{id}/access (reset to null)"
fi

# ---------------------------------------------------------------------------
# 12. Memories
# ---------------------------------------------------------------------------
section "12. Memories"

# Create a session memory (user_id must match GET/PUT/DELETE query default)
r=$(do_curl POST "/api/v1/memories" \
  -H "Content-Type: application/json" \
  -d "{
    \"memory_type\": \"session\",
    \"name\": \"test-session-curl\",
    \"user_id\": \"${TEST_USER_ID}\",
    \"device_id\": \"test-device-001\"
  }")
assert_status "$r" "201" "POST /api/v1/memories (create session)"

MEM_ID=$(json_get "$(body "$r")" "memory_id")
if [[ -n "$MEM_ID" ]]; then
  info "memory_id = $MEM_ID"
  CREATED_MEMORY_IDS+=("$MEM_ID")
else
  fail "No memory_id returned"
fi

# List memories
r=$(do_curl GET "/api/v1/memories?limit=10&user_id=${TEST_USER_ID}")
assert_status "$r" "200" "GET /api/v1/memories"

# Get the memory we just created
if [[ -n "$MEM_ID" ]]; then
  r=$(do_curl GET "/api/v1/memories/${MEM_ID}?user_id=${TEST_USER_ID}")
  assert_status "$r" "200" "GET /api/v1/memories/{memory_id}"

  # Associate test data with the memory
  if [[ -n "$DATA_ID_JSON" ]]; then
    r=$(do_curl POST "/api/v1/memories/${MEM_ID}/data?user_id=${TEST_USER_ID}" \
      -H "Content-Type: application/json" \
      -d "{\"data_ids\": [\"${DATA_ID_JSON}\"]}")
    assert_status "$r" "200" "POST /api/v1/memories/{id}/data (associate)"

    # Read data back from the memory
    r=$(do_curl GET "/api/v1/memories/${MEM_ID}/data?user_id=${TEST_USER_ID}")
    assert_status "$r" "200" "GET /api/v1/memories/{id}/data"
    COUNT=$(json_get "$(body "$r")" "total")
    info "items in memory = ${COUNT:-?}"

    # Remove data from memory (data stays, association removed)
    r=$(do_curl DELETE "/api/v1/memories/${MEM_ID}/data/${DATA_ID_JSON}?user_id=${TEST_USER_ID}")
    assert_status "$r" "200" "DELETE /api/v1/memories/{id}/data/{data_id} (disassociate)"
  fi

  # Update memory
  r=$(do_curl PUT "/api/v1/memories/${MEM_ID}?user_id=${TEST_USER_ID}" \
    -H "Content-Type: application/json" \
    -d '{"name": "updated-test-session", "active": false}')
  assert_status "$r" "200" "PUT /api/v1/memories/{id} (update)"
fi

# ---------------------------------------------------------------------------
# 13. Create data associated with a memory at upload time
# ---------------------------------------------------------------------------
section "13. Create Data with Memory Association"

if [[ -n "$MEM_ID" ]]; then
  r=$(do_curl POST "/api/v1/data" \
    -F 'content={"source": "memory-association-test"}' \
    -F "memory_ids=${MEM_ID}" \
    -F 'name=test_memory_linked')
  assert_status "$r" "200" "POST /api/v1/data with memory_ids"

  DATA_ID_MEM=$(json_get "$(body "$r")" "data_id")
  [[ -n "$DATA_ID_MEM" ]] && { info "data_id = $DATA_ID_MEM"; CREATED_DATA_IDS+=("$DATA_ID_MEM"); }
fi

# ---------------------------------------------------------------------------
# 14. Bulk delete (create 2 items and delete them together)
# ---------------------------------------------------------------------------
section "14. Bulk Delete"

r1=$(do_curl POST "/api/v1/data" -F 'content=bulk-test-1' -F 'name=bulk_test_1')
r2=$(do_curl POST "/api/v1/data" -F 'content=bulk-test-2' -F 'name=bulk_test_2')

B_ID1=$(json_get "$(body "$r1")" "data_id")
B_ID2=$(json_get "$(body "$r2")" "data_id")

if [[ -n "$B_ID1" && -n "$B_ID2" ]]; then
  info "bulk ids = $B_ID1, $B_ID2"
  r=$(do_curl POST "/api/v1/bulk/data/delete" \
    -H "Content-Type: application/json" \
    -d "{\"data_ids\": [\"${B_ID1}\", \"${B_ID2}\"]}")
  assert_status "$r" "200" "POST /api/v1/bulk/data/delete"

  DELETED=$(json_get "$(body "$r")" "deleted_count")
  if [[ "$DELETED" == "2" ]]; then
    pass "  Both items bulk-deleted (deleted_count=2)"
  else
    fail "  Expected deleted_count=2, got ${DELETED:-?}"
    # Don't leave them around
    CREATED_DATA_IDS+=("$B_ID1" "$B_ID2")
  fi
else
  fail "Could not create items for bulk delete test"
fi

# ---------------------------------------------------------------------------
# 15. Statistics (if endpoint exists)
# ---------------------------------------------------------------------------
section "15. Statistics"

r=$(do_curl GET "/api/v1/statistics")
CODE=$(http_code "$r")
if [[ "$CODE" == "200" ]]; then
  pass "GET /api/v1/statistics (HTTP 200)"
else
  skip "GET /api/v1/statistics (HTTP $CODE — endpoint may not be available)"
fi

# ---------------------------------------------------------------------------
# 16. PostgreSQL-backed AI tests (embeddings, viewpoints, semantic search)
# ---------------------------------------------------------------------------
section "16. Postgres / AI layer tests"

# Check if AI is enabled on this server
AI_STATUS=$(do_curl POST "/api/v1/ai/query/test")
AI_CODE=$(http_code "$AI_STATUS")
AI_BODY=$(body "$AI_STATUS")
POSTGRES_ENABLED=$(json_get "$AI_BODY" "postgres_enabled")

if [[ "$AI_CODE" == "200" && "$POSTGRES_ENABLED" == "true" ]]; then
  pass "AI layer reachable and postgres_enabled=true"

  # Need a data item to embed/analyse
  PG_DATA_ID="${CREATED_DATA_IDS[0]:-}"

  if [[ -n "$PG_DATA_ID" ]]; then
    # 16a. Create embedding
    r=$(do_curl POST "/api/v1/ai/embeddings" \
      -H "Content-Type: application/json" \
      -d "{\"data_id\": \"${PG_DATA_ID}\"}")
    EMB_CODE=$(http_code "$r")
    if [[ "$EMB_CODE" == "201" ]]; then
      EMB_ID=$(json_get "$(body "$r")" "embedding_id")
      pass "POST /api/v1/ai/embeddings (HTTP 201, id=${EMB_ID:0:12}…)"

      # 16b. List embeddings for data item
      r=$(do_curl GET "/api/v1/ai/embeddings?data_id=${PG_DATA_ID}")
      assert_status "$r" "200" "GET /api/v1/ai/embeddings?data_id=…"

      # 16c. Get embedding by ID
      if [[ -n "${EMB_ID:-}" ]]; then
        r=$(do_curl GET "/api/v1/ai/embeddings/${EMB_ID}")
        assert_status "$r" "200" "GET /api/v1/ai/embeddings/${EMB_ID:0:12}…"

        # 16d. Semantic search
        r=$(do_curl POST "/api/v1/ai/query/semantic" \
          -H "Content-Type: application/json" \
          -d '{"query": "test content", "max_results": 3}')
        SEM_CODE=$(http_code "$r")
        if [[ "$SEM_CODE" == "200" ]]; then
          pass "POST /api/v1/ai/query/semantic (HTTP 200)"
        else
          fail "POST /api/v1/ai/query/semantic (HTTP $SEM_CODE)"
        fi

        # 16e. Delete embedding
        r=$(do_curl DELETE "/api/v1/ai/embeddings/${EMB_ID}")
        assert_status "$r" "200" "DELETE /api/v1/ai/embeddings/${EMB_ID:0:12}…"
      fi
    else
      skip "POST /api/v1/ai/embeddings (HTTP ${EMB_CODE} — may require SYSTEM_GEMINI_API_KEY)"
    fi

    # 16f. Create viewpoint (requires AI key + prompt)
    # First create a simple prompt
    r=$(do_curl POST "/api/v1/ai/prompts" \
      -H "Content-Type: application/json" \
      -d "{\"name\": \"test-prompt\", \"template\": \"Summarise: {{content}}\"}")
    PROMPT_CODE=$(http_code "$r")
    if [[ "$PROMPT_CODE" == "201" ]]; then
      VP_PROMPT_ID=$(json_get "$(body "$r")" "prompt_id")
      CREATED_PROMPT_IDS+=("$VP_PROMPT_ID")

      r=$(do_curl POST "/api/v1/ai/viewpoints" \
        -H "Content-Type: application/json" \
        -d "{\"data_id\": \"${PG_DATA_ID}\", \"prompt_id\": \"${VP_PROMPT_ID}\"}")
      VP_CODE=$(http_code "$r")
      if [[ "$VP_CODE" == "201" ]]; then
        VP_ID=$(json_get "$(body "$r")" "viewpoint_id")
        pass "POST /api/v1/ai/viewpoints (HTTP 201)"
        CREATED_VIEWPOINT_IDS+=("$VP_ID")

        # 16g. Get viewpoint
        r=$(do_curl GET "/api/v1/ai/viewpoints/${VP_ID}")
        assert_status "$r" "200" "GET /api/v1/ai/viewpoints/${VP_ID:0:12}…"

        # 16h. List viewpoints for data
        r=$(do_curl GET "/api/v1/ai/viewpoints/data/${PG_DATA_ID}")
        assert_status "$r" "200" "GET /api/v1/ai/viewpoints/data/${PG_DATA_ID:0:12}…"
      else
        skip "POST /api/v1/ai/viewpoints (HTTP ${VP_CODE} — may require AI key)"
      fi
    else
      skip "Could not create prompt for viewpoint test"
    fi
  else
    skip "No data item available for AI tests"
  fi
else
  skip "AI layer tests (postgres_enabled=$POSTGRES_ENABLED, HTTP $AI_CODE)"
fi

# ---------------------------------------------------------------------------
# 17. Cleanup — delete all test data
# ---------------------------------------------------------------------------
section "17. Cleanup"

# Delete test viewpoints
for vp_id in "${CREATED_VIEWPOINT_IDS[@]:-}"; do
  [[ -z "$vp_id" ]] && continue
  r=$(do_curl DELETE "/api/v1/ai/viewpoints/${vp_id}")
  CODE=$(http_code "$r")
  if [[ "$CODE" == "200" ]]; then
    pass "DELETE /api/v1/ai/viewpoints/${vp_id:0:12}…"
  else
    fail "DELETE /api/v1/ai/viewpoints/${vp_id:0:12}… (HTTP $CODE)"
  fi
done

# Delete test prompts
for prompt_id in "${CREATED_PROMPT_IDS[@]:-}"; do
  [[ -z "$prompt_id" ]] && continue
  r=$(do_curl DELETE "/api/v1/ai/prompts/${prompt_id}")
  CODE=$(http_code "$r")
  [[ "$CODE" == "200" ]] && pass "DELETE /api/v1/ai/prompts/${prompt_id:0:12}…" || true
done

# Delete test memories (from section 17 original cleanup)
for mem_id in "${CREATED_MEMORY_IDS[@]:-}"; do
  [[ -z "$mem_id" ]] && continue
  r=$(do_curl DELETE "/api/v1/memories/${mem_id}?delete_data=false&user_id=${TEST_USER_ID}")
  CODE=$(http_code "$r")
  if [[ "$CODE" == "200" ]]; then
    pass "DELETE /api/v1/memories/${mem_id}"
  else
    fail "DELETE /api/v1/memories/${mem_id} (HTTP $CODE)"
  fi
done

# Delete test data items
for data_id in "${CREATED_DATA_IDS[@]:-}"; do
  [[ -z "$data_id" ]] && continue
  r=$(do_curl DELETE "/api/v1/data/${data_id}")
  CODE=$(http_code "$r")
  if [[ "$CODE" == "200" ]]; then
    pass "DELETE /api/v1/data/${data_id}"
  else
    fail "DELETE /api/v1/data/${data_id} (HTTP $CODE)"
  fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
TOTAL_TESTS=$(( PASS + FAIL + SKIP ))
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║               Test Results                   ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Total : ${TOTAL_TESTS}"
echo -e "  ${GREEN}Pass  : ${PASS}${NC}"
echo -e "  ${RED}Fail  : ${FAIL}${NC}"
echo -e "  ${YELLOW}Skip  : ${SKIP}${NC}"
echo ""

if [[ $FAIL -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}  All tests passed! 🎉${NC}"
  echo ""
  exit 0
else
  echo -e "${RED}${BOLD}  ${FAIL} test(s) failed.${NC}"
  echo ""
  exit 1
fi
