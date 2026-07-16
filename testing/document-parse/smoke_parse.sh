#!/usr/bin/env bash
# Smoke-test Phase 1 PDF parse: upload gold PDF, parse, persist via API.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

API="${MEM_DOG_API_URL:-http://localhost:8080}"
PDF="${1:-$ROOT/testing/document-parse/gold/car_insurance.pdf}"
USER_ID="${MEM_DOG_USER_ID:-00000000-0000-0000-0000-000000000001}"
PARSER="${DOCUMENT_PARSER:-pypdf}"
IMAGE="${DOCUMENT_PARSE_IMAGE:-mem-dog-webhook-processor:latest}"
API_KEY="${MEM_DOG_API_KEY:-}"

# Docker Desktop (macOS/Windows): --network host does not reach published host ports.
# Talk to the API via host.docker.internal from inside the container instead.
# Force with MEM_DOG_DOCKER_DESKTOP=1; override URL with MEM_DOG_DOCKER_API_URL.
_needs_docker_desktop_host=0
case "$(uname -s 2>/dev/null || true)" in
  Darwin|MINGW*|MSYS*|CYGWIN*) _needs_docker_desktop_host=1 ;;
esac
if [[ "${OS:-}" == "Windows_NT" || "${MEM_DOG_DOCKER_DESKTOP:-}" == "1" ]]; then
  _needs_docker_desktop_host=1
fi

DOCKER_API="$API"
DOCKER_NET=(--network host)
if [[ "$_needs_docker_desktop_host" == "1" ]]; then
  DOCKER_API="${MEM_DOG_DOCKER_API_URL:-http://host.docker.internal:8080}"
  DOCKER_NET=(--add-host=host.docker.internal:host-gateway)
fi

AUTH_HEADER=()
if [[ -n "$API_KEY" ]]; then
  AUTH_HEADER=(-H "x-api-key: ${API_KEY}")
fi

if [[ ! -f "$PDF" ]]; then
  echo "ERROR: PDF not found: $PDF" >&2
  exit 2
fi

BASENAME="$(basename "$PDF")"

echo "Uploading ${BASENAME}..."
CREATE=$(curl -sf ${AUTH_HEADER[@]+"${AUTH_HEADER[@]}"} -X POST "$API/api/v1/data" \
  -F "file=@${PDF};type=application/pdf" \
  -F "name=${BASENAME}" \
  -F "description=Phase 1 PDF parse smoke" \
  -F "owner_user_id=${USER_ID}")
DATA_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['data_id'])" <<<"$CREATE")
echo "data_id=$DATA_ID parser=$PARSER"

docker run --rm \
  "${DOCKER_NET[@]}" \
  -v "$ROOT/testing/document-parse/gold:/gold:ro" \
  -v "$ROOT/webhook/processor/webhook_agent:/app/webhook_agent:ro" \
  -w /app \
  -e PYTHONPATH=/app \
  -e DOCUMENT_PARSER="$PARSER" \
  -e MEM_DOG_API_URL="$DOCKER_API" \
  -e MEM_DOG_API_KEY="$API_KEY" \
  -e DATA_ID="$DATA_ID" \
  -e USER_ID="$USER_ID" \
  -e PDF_NAME="$BASENAME" \
  "$IMAGE" \
  python -c "
from pathlib import Path
import os, requests
from webhook_agent.document_parse import parse_document
b = Path('/gold/' + os.environ['PDF_NAME']).read_bytes()
doc = parse_document(b, 'application/pdf')
api = os.environ['MEM_DOG_API_URL']
key = os.environ.get('MEM_DOG_API_KEY') or ''
headers = {'x-api-key': key} if key else {}
data_id = os.environ['DATA_ID']
uid = os.environ['USER_ID']
r = requests.post(
    f'{api}/api/v1/data/{data_id}/parsed',
    params={'user_id': uid},
    headers=headers,
    json={'markdown': doc.markdown, 'document': doc.to_dict()},
    timeout=120,
)
r.raise_for_status()
print('parser=', doc.parser, 'pages=', doc.page_count, 'chars=', len(doc.markdown))
print('store=', r.json())
" 2>&1 | grep -v UserWarning | grep -v LiteLlm | grep -v 'return LiteLlm'

echo "GET parsed markdown (first 200 chars)..."
curl -sf ${AUTH_HEADER[@]+"${AUTH_HEADER[@]}"} "$API/api/v1/data/${DATA_ID}/parsed?user_id=${USER_ID}" | head -c 200
echo
echo "OK — parsed artifacts for $DATA_ID"
