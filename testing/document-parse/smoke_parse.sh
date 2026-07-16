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

if [[ ! -f "$PDF" ]]; then
  echo "ERROR: PDF not found: $PDF" >&2
  exit 2
fi

BASENAME="$(basename "$PDF")"

echo "Uploading ${BASENAME}..."
CREATE=$(curl -sf -X POST "$API/api/v1/data" \
  -F "file=@${PDF};type=application/pdf" \
  -F "name=${BASENAME}" \
  -F "description=Phase 1 PDF parse smoke" \
  -F "owner_user_id=${USER_ID}")
DATA_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['data_id'])" <<<"$CREATE")
echo "data_id=$DATA_ID parser=$PARSER"

docker run --rm \
  --network host \
  -v "$ROOT/testing/document-parse/gold:/gold:ro" \
  -v "$ROOT/webhook/processor/webhook_agent:/app/webhook_agent:ro" \
  -w /app \
  -e PYTHONPATH=/app \
  -e DOCUMENT_PARSER="$PARSER" \
  -e MEM_DOG_API_URL="$API" \
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
data_id = os.environ['DATA_ID']
uid = os.environ['USER_ID']
r = requests.post(
    f'{api}/api/v1/data/{data_id}/parsed',
    params={'user_id': uid},
    json={'markdown': doc.markdown, 'document': doc.to_dict()},
    timeout=120,
)
r.raise_for_status()
print('parser=', doc.parser, 'pages=', doc.page_count, 'chars=', len(doc.markdown))
print('store=', r.json())
" 2>&1 | grep -v UserWarning | grep -v LiteLlm | grep -v 'return LiteLlm'

echo "GET parsed markdown (first 200 chars)..."
curl -sf "$API/api/v1/data/${DATA_ID}/parsed?user_id=${USER_ID}" | head -c 200
echo
echo "OK — parsed artifacts for $DATA_ID"
