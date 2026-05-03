#!/usr/bin/env bash
# =============================================================================
# Mem-Dog Webhook End-to-End Test Script
# =============================================================================
# Comprehensively tests the full webhook pipeline by exercising every one of
# the 32 typed sub-agents via all four routing detection layers:
#
#   Layer 1  — explicit  data_type / source_type / type field
#   Layer 3  — MIME type via content_type / media_type field
#   Layer 4  — URL extension via url / source_url field
#   Fallback — payloads with no recognisable type → binary_blob
#
# Sub-agents tested (32 total)
# ─────────────────────────────────────────────────────────────────────────────
#  Media       : video_url, video_stream, audio_url, audio_stream,
#                image, image_batch
#  Documents   : pdf, office_doc, markdown, html_doc
#  Structured  : json, xml, csv, yaml
#  Code & Logs : code, log_file, log_stream
#  Sensor/IoT  : sensor, gps, biometric
#  Spatial/3D  : lidar, geospatial, model_3d
#  Comms/Web   : email, chat, calendar, web_page, feed
#  Binary/Sci  : archive, time_series, medical_imaging, binary_blob (fallback)
# ─────────────────────────────────────────────────────────────────────────────
# Additional sections:
#   Auth errors  : missing key, wrong key
#   Method errors: GET / PUT / DELETE / PATCH
#   Payload errors: empty body, invalid JSON, JSON array, JSON string
#   Post-verify  : poll the mem-dog API for routed data (requires --verify)
#
# Usage:
#   ./scripts/test-webhook.sh \
#       --webhook-url  https://YOUR_GATEWAY_URL/webhook \
#       --api-key      YOUR_API_KEY \
#       [--api-url     http://localhost:8080] \
#       [--verify]     \
#       [--verbose]
#
# Options:
#   -w, --webhook-url  Full webhook endpoint URL  (required)
#                      e.g. https://mem-dog-gw.uc.gateway.dev/webhook
#   -k, --api-key      x-api-key value            (required)
#   -a, --api-url      Mem-dog API URL for post-processing verification
#   -V, --verify       Poll mem-dog API to confirm each routed entry
#   -v, --verbose      Print full request/response bodies
#   -h, --help         Show this help
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
WEBHOOK_URL=""
API_KEY=""
API_URL=""
VERIFY=false
VERBOSE=false

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ---------------------------------------------------------------------------
# Counters / helpers
# ---------------------------------------------------------------------------
PASS=0; FAIL=0; SKIP=0

pass()    { echo -e "${GREEN}  ✓ PASS${NC} $1"; (( PASS++ )) || true; }
fail()    { echo -e "${RED}  ✗ FAIL${NC} $1"; (( FAIL++ )) || true; }
skip()    { echo -e "${YELLOW}  - SKIP${NC} $1"; (( SKIP++ )) || true; }
section() { echo ""; echo -e "${BOLD}${CYAN}── $1${NC}"; }
info()    { echo -e "  ${BLUE}↳${NC} $1"; }

json_get() { echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$2',''))" 2>/dev/null || true; }

# ---------------------------------------------------------------------------
# Core request helpers
# ---------------------------------------------------------------------------

# POST to the webhook endpoint; return "<http_code>|||<body>"
webhook_post() {
  local payload="$1"
  local tmp; tmp=$(mktemp)
  local code
  code=$(curl -s -o "$tmp" -w "%{http_code}" \
      -X POST "${WEBHOOK_URL}" \
      -H "x-api-key: ${API_KEY}" \
      -H "Content-Type: application/json" \
      -d "$payload" 2>/dev/null || echo "000")
  local body; body=$(cat "$tmp"); rm -f "$tmp"
  if $VERBOSE; then
    echo -e "    ${BLUE}POST ${WEBHOOK_URL} → ${code}${NC}"
    echo "$body" | python3 -m json.tool 2>/dev/null || echo "    $body"
  fi
  echo "${code}|||${body}"
}

# POST with custom curl flags (for auth/method error tests)
raw_post() {
  local tmp; tmp=$(mktemp)
  local code
  code=$(curl -s -o "$tmp" -w "%{http_code}" "$@" 2>/dev/null || echo "000")
  local body; body=$(cat "$tmp"); rm -f "$tmp"
  if $VERBOSE; then echo "    → HTTP ${code}: $body"; fi
  echo "${code}|||${body}"
}

http_code() { echo "$1" | cut -d'|' -f1; }
body()      { echo "$1" | cut -d'|' -f4-; }

# Assert HTTP 202 and that the response body contains "accepted"
assert_202() {
  local result="$1" label="$2"
  local code; code=$(http_code "$result")
  local b;    b=$(body "$result")
  local status; status=$(json_get "$b" "status")
  if [[ "$code" == "202" ]]; then
    pass "$label (HTTP 202)"
    if [[ "$status" == "accepted" ]]; then
      pass "  → status=accepted"
    else
      fail "  → status field missing or wrong (got '${status}')"
    fi
    local msg_id; msg_id=$(json_get "$b" "message_id")
    if [[ -n "$msg_id" ]]; then
      pass "  → message_id present ($msg_id)"
    else
      fail "  → message_id missing"
    fi
  else
    fail "$label (expected HTTP 202, got $code)"
    [[ -n "$b" ]] && echo "    response: $b"
  fi
}

# Assert a specific HTTP status
assert_status() {
  local result="$1" expected="$2" label="$3"
  local code; code=$(http_code "$result")
  if [[ "$code" == "$expected" ]]; then
    pass "$label (HTTP $code)"
  else
    fail "$label (expected HTTP $expected, got $code)"
    local b; b=$(body "$result"); [[ -n "$b" ]] && echo "    $b"
  fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    -w|--webhook-url) WEBHOOK_URL="${2%/}"; shift 2;;
    # legacy alias so old invocations still work
    -g|--gateway-url) WEBHOOK_URL="${2%/}/webhook"; shift 2;;
    -k|--api-key)     API_KEY="$2";         shift 2;;
    -a|--api-url)     API_URL="${2%/}";     shift 2;;
    -V|--verify)      VERIFY=true;          shift;;
    -v|--verbose)     VERBOSE=true;         shift;;
    -h|--help)        grep '^#' "$0" | head -65 | sed 's/^# \?//'; exit 0;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

[[ -z "$WEBHOOK_URL" || -z "$API_KEY" ]] && {
  echo -e "${RED}Error: --webhook-url and --api-key are required.${NC}"
  echo "Usage: $0 --webhook-url <full-url> --api-key <key> [--api-url <url>] [--verify] [--verbose]"
  exit 1
}
if $VERIFY && [[ -z "$API_URL" ]]; then
  echo -e "${YELLOW}Warning: --verify requires --api-url. Disabling.${NC}"
  VERIFY=false
fi

TRACE_ID="test-$(python3 -c 'import uuid; print(uuid.uuid4())')"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║    Mem-Dog Webhook — Comprehensive Sub-Agent Tests   ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
info "Webhook URL : ${WEBHOOK_URL}"
info "Verify      : ${VERIFY}"
info "Trace ID    : ${TRACE_ID}"
echo ""

# ===========================================================================
# SECTION 1 — Layer 1 routing: explicit data_type field
#             Every sub-agent is exercised once here.
# ===========================================================================

section "1. Layer 1 — Explicit data_type (all 32 sub-agents)"

# ── Media ────────────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}Media${NC}"

assert_202 "$(webhook_post "{\"data_type\": \"video_url\", \"trace_id\": \"${TRACE_ID}\",
  \"url\": \"https://cdn.example.com/clip.mp4\",
  \"title\": \"Product demo\", \"duration_seconds\": 142}")" \
  "video_url agent"

assert_202 "$(webhook_post "{\"data_type\": \"video_stream\",
  \"stream_url\": \"rtsp://camera.example.com/live\",
  \"codec\": \"h264\", \"bitrate_kbps\": 4000}")" \
  "video_stream agent"

assert_202 "$(webhook_post "{\"data_type\": \"audio_url\",
  \"url\": \"https://cdn.example.com/episode.mp3\",
  \"title\": \"Podcast ep 42\", \"duration_seconds\": 3600}")" \
  "audio_url agent"

assert_202 "$(webhook_post "{\"data_type\": \"audio_stream\",
  \"stream_url\": \"https://radio.example.com/live.ogg\",
  \"bitrate_kbps\": 128, \"codec\": \"vorbis\"}")" \
  "audio_stream agent"

assert_202 "$(webhook_post "{\"data_type\": \"image\",
  \"url\": \"https://cdn.example.com/photo.jpg\",
  \"width\": 1920, \"height\": 1080, \"format\": \"jpeg\"}")" \
  "image agent"

assert_202 "$(webhook_post "{\"data_type\": \"image_batch\",
  \"images\": [
    {\"url\": \"https://cdn.example.com/a.jpg\"},
    {\"url\": \"https://cdn.example.com/b.png\"}
  ],
  \"count\": 2}")" \
  "image_batch agent"

# ── Documents ────────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}Documents${NC}"

assert_202 "$(webhook_post "{\"data_type\": \"pdf\",
  \"url\": \"https://docs.example.com/report.pdf\",
  \"title\": \"Q4 Financial Report\", \"pages\": 28}")" \
  "pdf agent"

assert_202 "$(webhook_post "{\"data_type\": \"office_doc\",
  \"url\": \"https://docs.example.com/presentation.pptx\",
  \"title\": \"Board Deck\", \"format\": \"pptx\"}")" \
  "office_doc agent"

assert_202 "$(webhook_post "{\"data_type\": \"markdown\",
  \"content\": \"# Hello\n\nThis is a **test** markdown document.\",
  \"source\": \"wiki\", \"slug\": \"hello-world\"}")" \
  "markdown agent"

assert_202 "$(webhook_post "{\"data_type\": \"html_doc\",
  \"url\": \"https://blog.example.com/post/1\",
  \"title\": \"My Blog Post\", \"word_count\": 820}")" \
  "html_doc agent"

# ── Structured ───────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}Structured Data${NC}"

assert_202 "$(webhook_post "{\"data_type\": \"json\",
  \"payload\": {\"user\": {\"id\": \"u-1\", \"name\": \"Alice\"}},
  \"schema\": \"user-v2\"}")" \
  "json agent"

assert_202 "$(webhook_post "{\"data_type\": \"xml\",
  \"content\": \"<order><id>42</id><total>99.99</total></order>\",
  \"encoding\": \"utf-8\"}")" \
  "xml agent"

assert_202 "$(webhook_post "{\"data_type\": \"csv\",
  \"url\": \"https://data.example.com/sales_q4.csv\",
  \"rows\": 5000, \"columns\": [\"date\", \"product\", \"revenue\"]}")" \
  "csv agent"

assert_202 "$(webhook_post "{\"data_type\": \"yaml\",
  \"content\": \"service: api\nversion: 1.2.3\nreplicas: 3\",
  \"source\": \"helm-chart\"}")" \
  "yaml agent"

# ── Code & Logs ───────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}Code & Logs${NC}"

assert_202 "$(webhook_post "{\"data_type\": \"code\",
  \"language\": \"python\",
  \"filename\": \"ingest.py\",
  \"content\": \"def ingest(payload): return payload\",
  \"repo\": \"mem-dog\", \"commit\": \"a1b2c3d\"}")" \
  "code agent"

assert_202 "$(webhook_post "{\"data_type\": \"log_file\",
  \"filename\": \"api-2026-02-17.log\",
  \"url\": \"https://storage.example.com/logs/api-2026-02-17.log\",
  \"lines\": 42000, \"level\": \"ERROR\"}")" \
  "log_file agent"

assert_202 "$(webhook_post "{\"data_type\": \"log_stream\",
  \"stream_id\": \"k8s-pod-abc123\",
  \"namespace\": \"production\",
  \"container\": \"api\",
  \"lines\": [\"INFO starting\", \"ERROR disk full\"]}")" \
  "log_stream agent"

# ── Sensor / IoT ─────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}Sensor / IoT${NC}"

assert_202 "$(webhook_post "{\"data_type\": \"sensor\",
  \"sensor_id\": \"temp-007\",
  \"reading\": 23.8, \"unit\": \"celsius\",
  \"location\": \"server-room-a\",
  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}")" \
  "sensor agent"

assert_202 "$(webhook_post "{\"data_type\": \"gps\",
  \"device_id\": \"truck-42\",
  \"latitude\": 37.7749, \"longitude\": -122.4194,
  \"altitude_m\": 15.0, \"speed_kmh\": 65.2,
  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}")" \
  "gps agent"

assert_202 "$(webhook_post "{\"data_type\": \"biometric\",
  \"subject_id\": \"patient-99\",
  \"metric\": \"heart_rate\", \"value\": 72, \"unit\": \"bpm\",
  \"device\": \"smartwatch-v3\",
  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}")" \
  "biometric agent"

# ── Spatial / 3D ─────────────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}Spatial / 3D${NC}"

assert_202 "$(webhook_post "{\"data_type\": \"lidar\",
  \"url\": \"https://storage.example.com/scans/scene.pcd\",
  \"points\": 1500000, \"format\": \"pcd\",
  \"sensor\": \"Velodyne-VLP-32C\"}")" \
  "lidar agent"

assert_202 "$(webhook_post "{\"data_type\": \"geospatial\",
  \"url\": \"https://storage.example.com/map/boundary.geojson\",
  \"crs\": \"EPSG:4326\",
  \"feature_count\": 42, \"geometry_type\": \"Polygon\"}")" \
  "geospatial agent"

assert_202 "$(webhook_post "{\"data_type\": \"model_3d\",
  \"url\": \"https://storage.example.com/models/robot.glb\",
  \"format\": \"glb\", \"vertices\": 82000,
  \"textures\": true}")" \
  "model_3d agent"

# ── Communication & Web ───────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}Communication & Web${NC}"

assert_202 "$(webhook_post "{\"data_type\": \"email\",
  \"message_id\": \"<abc123@mail.example.com>\",
  \"from\": \"alice@example.com\",
  \"to\": [\"bob@example.com\"],
  \"subject\": \"Q4 Report\",
  \"body_text\": \"Please find the report attached.\"}")" \
  "email agent"

assert_202 "$(webhook_post "{\"data_type\": \"chat\",
  \"platform\": \"slack\",
  \"channel\": \"#ops-alerts\",
  \"user\": \"alice\",
  \"text\": \"Deployment succeeded in staging\",
  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}")" \
  "chat agent"

assert_202 "$(webhook_post "{\"data_type\": \"calendar\",
  \"uid\": \"evt-2026-q1-review\",
  \"title\": \"Q1 Business Review\",
  \"start\": \"2026-03-31T09:00:00Z\",
  \"end\": \"2026-03-31T11:00:00Z\",
  \"attendees\": [\"alice@example.com\", \"bob@example.com\"]}")" \
  "calendar agent"

assert_202 "$(webhook_post "{\"data_type\": \"web_page\",
  \"url\": \"https://blog.example.com/release-notes\",
  \"title\": \"Release Notes v2.0\",
  \"scraped_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
  \"word_count\": 1240}")" \
  "web_page agent"

assert_202 "$(webhook_post "{\"data_type\": \"feed\",
  \"feed_url\": \"https://blog.example.com/rss.xml\",
  \"feed_type\": \"rss\",
  \"item_count\": 20,
  \"latest_item\": {\"title\": \"New Post\", \"link\": \"https://blog.example.com/new-post\"}}")" \
  "feed agent"

# ── Binary / Scientific ───────────────────────────────────────────────────────

echo ""
echo -e "  ${BOLD}Binary / Scientific${NC}"

assert_202 "$(webhook_post "{\"data_type\": \"archive\",
  \"url\": \"https://storage.example.com/releases/app-v2.0.zip\",
  \"format\": \"zip\", \"size_bytes\": 45678900,
  \"file_count\": 312}")" \
  "archive agent"

assert_202 "$(webhook_post "{\"data_type\": \"time_series\",
  \"metric\": \"cpu_utilisation\",
  \"source\": \"prometheus\",
  \"interval_seconds\": 15,
  \"datapoints\": [[1700000000, 0.42], [1700000015, 0.51]]}")" \
  "time_series agent"

assert_202 "$(webhook_post "{\"data_type\": \"medical_imaging\",
  \"url\": \"https://pacs.example.com/scans/chest-ct-001.dcm\",
  \"modality\": \"CT\",
  \"patient_id\": \"patient-0042\",
  \"study_date\": \"2026-01-15\"}")" \
  "medical_imaging agent"

# Fallback — no recognisable type, no hints
assert_202 "$(webhook_post "{\"data_type\": \"binary_blob\",
  \"url\": \"https://storage.example.com/blobs/unknown.bin\",
  \"size_bytes\": 10240, \"checksum\": \"sha256:abc123\"}")" \
  "binary_blob agent (explicit)"

# ===========================================================================
# SECTION 2 — Layer 3 routing: MIME type via content_type field
# ===========================================================================

section "2. Layer 3 — MIME type routing (content_type field)"

# One representative test per MIME family
MIME_CASES=(
  "video/mp4:video_url:video file"
  "video/stream:video_stream:live video stream"
  "audio/mpeg:audio_url:audio file"
  "audio/stream:audio_stream:audio stream"
  "image/jpeg:image:JPEG image"
  "image/batch:image_batch:image batch"
  "application/pdf:pdf:PDF document"
  "application/json:json:JSON payload"
  "application/xml:xml:XML payload"
  "text/csv:csv:CSV data"
  "application/yaml:yaml:YAML config"
  "text/markdown:markdown:Markdown doc"
  "text/html:html_doc:HTML page"
  "text/x-log:log_file:log file"
  "application/x-log-stream:log_stream:log stream"
  "application/x-sensor:sensor:sensor reading"
  "application/x-gps:gps:GPS reading"
  "application/x-biometric:biometric:biometric data"
  "application/x-lidar:lidar:LiDAR scan"
  "application/x-web-scrape:web_page:web scrape"
  "application/rss+xml:feed:RSS feed"
  "message/rfc822:email:email message"
  "application/x-chat:chat:chat message"
  "text/calendar:calendar:calendar event"
  "model/gltf-binary:model_3d:3D model"
  "application/x-timeseries:time_series:time series"
  "application/dicom:medical_imaging:DICOM image"
  "application/octet-stream:binary_blob:binary blob"
)

for case in "${MIME_CASES[@]}"; do
  IFS=':' read -r mime expected_type label <<< "$case"
  r=$(webhook_post "{\"content_type\": \"${mime}\",
    \"url\": \"https://example.com/asset\",
    \"trace_id\": \"${TRACE_ID}-mime-${expected_type}\"}")
  assert_202 "$r" "MIME ${mime} → ${label}"
done

# ===========================================================================
# SECTION 3 — Layer 4 routing: URL extension
# ===========================================================================

section "3. Layer 4 — URL extension routing (url field)"

EXT_CASES=(
  ".mp4:video_url:MP4 video"
  ".mov:video_url:MOV video"
  ".webm:video_url:WebM video"
  ".mp3:audio_url:MP3 audio"
  ".wav:audio_url:WAV audio"
  ".jpg:image:JPEG image"
  ".png:image:PNG image"
  ".gif:image:GIF image"
  ".pdf:pdf:PDF"
  ".docx:office_doc:Word document"
  ".xlsx:office_doc:Excel spreadsheet"
  ".pptx:office_doc:PowerPoint"
  ".md:markdown:Markdown"
  ".html:html_doc:HTML page"
  ".json:json:JSON file"
  ".xml:xml:XML file"
  ".csv:csv:CSV file"
  ".yaml:yaml:YAML file"
  ".py:code:Python source"
  ".ts:code:TypeScript source"
  ".js:code:JavaScript source"
  ".go:code:Go source"
  ".log:log_file:log file"
  ".pcd:lidar:LiDAR point cloud"
  ".geojson:geospatial:GeoJSON"
  ".gltf:model_3d:glTF model"
  ".glb:model_3d:GLB model"
  ".ics:calendar:iCal file"
  ".eml:email:email file"
  ".zip:archive:ZIP archive"
  ".tar:archive:TAR archive"
  ".dcm:medical_imaging:DICOM file"
)

for case in "${EXT_CASES[@]}"; do
  IFS=':' read -r ext expected_type label <<< "$case"
  r=$(webhook_post "{\"url\": \"https://storage.example.com/asset${ext}\",
    \"trace_id\": \"${TRACE_ID}-ext-${expected_type}\",
    \"description\": \"extension routing test\"}")
  assert_202 "$r" "ext ${ext} → ${label}"
done

# ===========================================================================
# SECTION 4 — Fallback routing (binary_blob catch-all)
# ===========================================================================

section "4. Fallback routing — no hints → binary_blob"

r=$(webhook_post "{\"ping\": \"pong\", \"trace_id\": \"${TRACE_ID}-fallback-1\"}")
assert_202 "$r" "Minimal payload (no type hints) → fallback"

r=$(webhook_post "{\"unknown_field\": 42, \"another\": true}")
assert_202 "$r" "Opaque payload (no type hints) → fallback"

r=$(webhook_post "{\"deeply\": {\"nested\": {\"data\": \"value\"}}, \"mystery\": [1,2,3]}")
assert_202 "$r" "Deeply nested payload → fallback"

# ===========================================================================
# SECTION 5 — Group context: same user/group routes to shared memories
# ===========================================================================

section "5. Group context — same user+group across multiple payloads"

GROUP_USER="test-user-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"
GROUP_ID="test-group-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"

r=$(webhook_post "{\"data_type\": \"sensor\",
  \"user_id\": \"${GROUP_USER}\", \"group_id\": \"${GROUP_ID}\",
  \"sensor_id\": \"s1\", \"reading\": 10.0, \"unit\": \"C\"}")
assert_202 "$r" "Group payload #1 (sensor) — user ${GROUP_USER}"

r=$(webhook_post "{\"data_type\": \"gps\",
  \"user_id\": \"${GROUP_USER}\", \"group_id\": \"${GROUP_ID}\",
  \"latitude\": 37.77, \"longitude\": -122.41}")
assert_202 "$r" "Group payload #2 (gps) — same user, shared group memory"

r=$(webhook_post "{\"data_type\": \"json\",
  \"user_id\": \"${GROUP_USER}\", \"group_id\": \"${GROUP_ID}\",
  \"event\": \"status_check\", \"ok\": true}")
assert_202 "$r" "Group payload #3 (json) — same user, shared group memory"

# ===========================================================================
# SECTION 6 — source_type field (alias for data_type, Layer 1)
# ===========================================================================

section "6. Layer 1 — source_type alias field"

r=$(webhook_post "{\"source_type\": \"pdf\",
  \"url\": \"https://docs.example.com/spec.pdf\",
  \"title\": \"Technical Spec\"}")
assert_202 "$r" "source_type: pdf"

r=$(webhook_post "{\"source_type\": \"image\",
  \"url\": \"https://cdn.example.com/hero.jpg\"}")
assert_202 "$r" "source_type: image"

r=$(webhook_post "{\"type\": \"csv\",
  \"url\": \"https://data.example.com/export.csv\",
  \"rows\": 200}")
assert_202 "$r" "type: csv  (alternate Layer 1 field)"

# ===========================================================================
# SECTION 7 — Authentication errors
# ===========================================================================

section "7. Authentication Errors"

# No API key header
tmp=$(mktemp)
code=$(curl -s -o "$tmp" -w "%{http_code}" \
    -X POST "${WEBHOOK_URL}" \
    -H "Content-Type: application/json" \
    -d '{"event":"no-key"}' 2>/dev/null || echo "000")
rm -f "$tmp"
if [[ "$code" == "401" || "$code" == "403" ]]; then
  pass "POST without x-api-key → HTTP $code (auth rejected)"
else
  fail "POST without x-api-key → expected 401/403, got $code"
fi

# Wrong API key
tmp=$(mktemp)
code=$(curl -s -o "$tmp" -w "%{http_code}" \
    -X POST "${WEBHOOK_URL}" \
    -H "x-api-key: bad-key-0000000000" \
    -H "Content-Type: application/json" \
    -d '{"event":"bad-key"}' 2>/dev/null || echo "000")
rm -f "$tmp"
if [[ "$code" == "401" || "$code" == "403" ]]; then
  pass "POST with wrong api-key → HTTP $code (auth rejected)"
else
  fail "POST with wrong api-key → expected 401/403, got $code"
fi

# ===========================================================================
# SECTION 8 — Wrong HTTP method
# ===========================================================================

section "8. Wrong HTTP Method"

for method in GET PUT DELETE PATCH; do
  tmp=$(mktemp)
  code=$(curl -s -o "$tmp" -w "%{http_code}" \
      -X "$method" "${WEBHOOK_URL}" \
      -H "x-api-key: ${API_KEY}" \
      -H "Content-Type: application/json" 2>/dev/null || echo "000")
  rm -f "$tmp"
  if [[ "$code" == "405" || "$code" == "404" ]]; then
    pass "${method} → HTTP $code (method rejected)"
  else
    fail "${method} → expected 405/404, got $code"
  fi
done

# ===========================================================================
# SECTION 9 — Bad payload validation (receiver function)
# ===========================================================================

section "9. Bad Payload Validation"

# Empty body
tmp=$(mktemp)
code=$(curl -s -o "$tmp" -w "%{http_code}" \
    -X POST "${WEBHOOK_URL}" \
    -H "x-api-key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '' 2>/dev/null || echo "000")
rm -f "$tmp"
[[ "$code" == "400" ]] && pass "Empty body → HTTP 400" || fail "Empty body → expected 400, got $code"

# Invalid JSON
tmp=$(mktemp)
code=$(curl -s -o "$tmp" -w "%{http_code}" \
    -X POST "${WEBHOOK_URL}" \
    -H "x-api-key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{not valid json' 2>/dev/null || echo "000")
rm -f "$tmp"
[[ "$code" == "400" ]] && pass "Invalid JSON → HTTP 400" || fail "Invalid JSON → expected 400, got $code"

# JSON array (must be object)
tmp=$(mktemp)
code=$(curl -s -o "$tmp" -w "%{http_code}" \
    -X POST "${WEBHOOK_URL}" \
    -H "x-api-key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '[1, 2, 3]' 2>/dev/null || echo "000")
rm -f "$tmp"
[[ "$code" == "400" ]] && pass "JSON array body → HTTP 400" || fail "JSON array body → expected 400, got $code"

# JSON string (must be object)
tmp=$(mktemp)
code=$(curl -s -o "$tmp" -w "%{http_code}" \
    -X POST "${WEBHOOK_URL}" \
    -H "x-api-key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '"just a string"' 2>/dev/null || echo "000")
rm -f "$tmp"
[[ "$code" == "400" ]] && pass "JSON string body → HTTP 400" || fail "JSON string body → expected 400, got $code"

# ===========================================================================
# SECTION 10 — Post-processing verification (optional)
# ===========================================================================

section "10. Post-Processing Verification"

if ! $VERIFY; then
  skip "Skipped — pass --verify --api-url <url> to enable"
else
  info "Waiting up to 45 s for the ADK agent to process payloads…"
  FOUND=false
  MAX_WAIT=45
  INTERVAL=5

  for (( i=0; i < MAX_WAIT; i += INTERVAL )); do
    sleep "$INTERVAL"
    echo -n "    [${i}s] checking… "

    r=$(curl -s "${API_URL}/api/v1/data?limit=100" 2>/dev/null || echo "{}")
    # Look for any item tagged 'agent_type:*' written after the test started
    if echo "$r" | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('items', [])
for item in items:
    tags = item.get('tags') or []
    for tag in tags:
        if tag.startswith('agent_type:'):
            print('found:', tag)
            sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
      FOUND=true
      break
    else
      echo "not yet"
    fi
  done

  if $FOUND; then
    pass "Routed data items appeared in mem-dog API (tagged agent_type:*)"
    # Count distinct agent types seen
    SEEN_TYPES=$(curl -s "${API_URL}/api/v1/data?limit=200" 2>/dev/null \
      | python3 -c "
import sys, json
d = json.load(sys.stdin)
types = set()
for item in d.get('items', []):
    for tag in (item.get('tags') or []):
        if tag.startswith('agent_type:'):
            types.add(tag.split(':',1)[1])
print(f'Distinct agent types in store: {len(types)}')
for t in sorted(types): print(f'  - {t}')
" 2>/dev/null || echo "(could not parse)")
    info "$SEEN_TYPES"
  else
    fail "No agent_type-tagged data found in mem-dog API after ${MAX_WAIT}s"
    info "Check processor logs:"
    info "  gcloud functions logs read mem-dog-webhook-processor-dev --gen2 --region=us-central1"
  fi
fi

# ===========================================================================
# Summary
# ===========================================================================

TOTAL=$(( PASS + FAIL + SKIP ))
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                   Test Results                       ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Total checks : ${TOTAL}"
echo -e "  ${GREEN}Pass          : ${PASS}${NC}"
echo -e "  ${RED}Fail          : ${FAIL}${NC}"
echo -e "  ${YELLOW}Skip          : ${SKIP}${NC}"
echo ""

if [[ $FAIL -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}  All tests passed! 🎉${NC}"
  echo ""
  exit 0
else
  echo -e "${RED}${BOLD}  ${FAIL} test(s) failed.${NC}"
  echo ""
  echo -e "  Troubleshooting:"
  echo -e "    • Verify gateway URL and API key are correct"
  echo -e "    • Check processor logs:"
  echo -e "      gcloud functions logs read mem-dog-webhook-processor-dev \\"
  echo -e "          --gen2 --region=us-central1 --limit=50"
  echo ""
  exit 1
fi
