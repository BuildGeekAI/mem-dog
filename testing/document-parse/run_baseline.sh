#!/usr/bin/env bash
# Run Phase 0 baseline harness using the webhook-processor image (has pypdf).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GOLD="$ROOT/testing/document-parse/gold"
OUT_DIR="$ROOT/testing/document-parse/out"
mkdir -p "$OUT_DIR"

if [[ ! -d "$GOLD" ]] || [[ -z "$(ls -A "$GOLD" 2>/dev/null || true)" ]]; then
  echo "ERROR: place fixtures under testing/document-parse/gold/" >&2
  exit 2
fi

IMAGE="${DOCUMENT_PARSE_BASELINE_IMAGE:-mem-dog-webhook-processor:latest}"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Building webhook-processor image..."
  docker compose build webhook-processor
fi

docker run --rm \
  -v "$ROOT/testing/document-parse:/work/testing/document-parse" \
  -v "$ROOT/webhook/processor/webhook_agent:/app/webhook_agent:ro" \
  -w /app \
  -e PYTHONPATH=/app \
  "$IMAGE" \
  python /work/testing/document-parse/baseline_harness.py \
    --gold /work/testing/document-parse/gold \
    --manifest /work/testing/document-parse/manifest.json \
    --json /work/testing/document-parse/out/baseline-latest.json

echo "Results: testing/document-parse/out/baseline-latest.json"
