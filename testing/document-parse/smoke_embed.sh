#!/usr/bin/env bash
# Phase 2 smoke: parsed body → embed → semantic search with page metadata.
# Requires lean API up (./scripts/dev-lean.sh up -d) and a cloud embedding key in api/.env.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

API="${MEM_DOG_API_URL:-http://localhost:8080}"
PDF="${1:-$ROOT/testing/document-parse/gold/car_insurance.pdf}"
USER_ID="${MEM_DOG_USER_ID:-00000000-0000-0000-0000-000000000001}"
PARSER="${DOCUMENT_PARSER:-docling}"
IMAGE="${DOCUMENT_PARSE_IMAGE:-mem-dog-webhook-processor:latest}"
QUERY="${SEMANTIC_QUERY:-comprehensive car insurance}"
API_KEY="${MEM_DOG_API_KEY:-}"

# Docker Desktop (macOS/Windows): --network host does not reach published host ports.
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
  -F "description=Phase 2 embed+search smoke" \
  -F "owner_user_id=${USER_ID}")
DATA_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['data_id'])" <<<"$CREATE")
echo "data_id=$DATA_ID parser=$PARSER"

echo "Parsing + persisting..."
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
print('parser=', doc.parser, 'pages=', doc.page_count, 'chunks=', len(doc.chunks or []))
" 2>&1 | grep -v UserWarning | grep -v LiteLlm | grep -v 'return LiteLlm'

echo "Creating embeddings from parsed body..."
EMB=$(curl -sf ${AUTH_HEADER[@]+"${AUTH_HEADER[@]}"} -X POST "$API/api/v1/ai/embeddings" \
  -H 'Content-Type: application/json' \
  -d "{\"data_id\":\"${DATA_ID}\",\"user_id\":\"${USER_ID}\"}")
python3 -c "import json,sys; d=json.load(sys.stdin); print('embedding_id=', d.get('embedding_id'), 'page=', d.get('page'), 'kind=', d.get('embedding_kind'))" <<<"$EMB"

echo "Semantic search: query=${QUERY}"
SEARCH=$(curl -sf ${AUTH_HEADER[@]+"${AUTH_HEADER[@]}"} -X POST "$API/api/v1/ai/query/semantic" \
  -H 'Content-Type: application/json' \
  -d "{\"query\":\"${QUERY}\",\"user_id\":\"${USER_ID}\",\"max_results\":5}")
SEARCH="$SEARCH" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["SEARCH"])
records = data.get("records") or []
print(f"records={len(records)} latency_ms={data.get('latency_ms')}")
ok = False
body_hit = False
for rec in records:
    for ch in rec.get("matching_chunks") or []:
        page = ch.get("page")
        snippet = (ch.get("chunk_text") or "")[:80].replace("\n", " ")
        print(f"  data_id={rec.get('data_id')} page={page} sim={ch.get('similarity')} snippet={snippet!r}")
        if page is not None:
            ok = True
        if "insurance" in snippet.lower() or "cover" in snippet.lower() or "policy" in snippet.lower():
            body_hit = True
if not records:
    raise SystemExit("FAIL: no semantic records")
if not ok:
    print("WARN: no page on matching chunks (parsed JSON chunks may be missing page)")
else:
    print("OK — body chunks retrieved with page metadata")
if body_hit:
    print("OK — matched body-like phrase in chunk text")
PY
