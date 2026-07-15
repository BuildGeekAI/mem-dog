#!/usr/bin/env bash
# Start (or manage) the lean local stack for ≤16GB machines.
#
# Services: db + redis + neo4j + api + ui + mcp-server + webhook-gateway + webhook-processor
# Skips: ollama-* — use host Ollama (Metal GPU) or cloud keys instead
#
# DOCUMENT_PARSER defaults to pypdf; opt into Docling with DOCUMENT_PARSER=docling.
#
# Usage:
#   ./scripts/dev-lean.sh up [-d]
#   DOCUMENT_PARSER=docling ./scripts/dev-lean.sh up -d
#   ./scripts/dev-lean.sh down
#   ./scripts/dev-lean.sh ps
#   ./scripts/dev-lean.sh logs [service]
#   ./scripts/dev-lean.sh config   # print merged compose config

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.lean.yml)
SERVICES=(db redis neo4j api ui mcp-server webhook-gateway webhook-processor)

warn_resources() {
  local mem_mib=""
  local settings="$HOME/Library/Group Containers/group.com.docker/settings-store.json"
  if [[ -f "$settings" ]]; then
    mem_mib="$(python3 -c "import json; print(json.load(open('$settings')).get('MemoryMiB',''))" 2>/dev/null || true)"
  fi
  if [[ -n "$mem_mib" && "$mem_mib" -lt 10240 ]]; then
    echo "WARN: Docker Desktop MemoryMiB=${mem_mib} (< 10240)." >&2
    echo "      Prefer 10–12 GB if using DOCUMENT_PARSER=docling on a 16GB Mac mini." >&2
  fi
  local env_file="$ROOT/api/.env"
  local has_key=0
  if [[ -f "$env_file" ]]; then
    if grep -Eiq '^(OLLAMA_CLOUD_API_KEY|SYSTEM_GEMINI_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY)=.+' "$env_file"; then
      has_key=1
    fi
  fi
  if [[ -n "${OLLAMA_CLOUD_API_KEY:-}${SYSTEM_GEMINI_API_KEY:-}${GEMINI_API_KEY:-}${OPENAI_API_KEY:-}" ]]; then
    has_key=1
  fi
  if [[ "$has_key" -eq 0 ]]; then
    echo "WARN: No cloud AI key found." >&2
    echo "      Create api/.env (from api/.env.example) and set OLLAMA_CLOUD_API_KEY=..." >&2
    echo "      (or SYSTEM_GEMINI_API_KEY / OPENAI_API_KEY). Compose loads api/.env into api + processor." >&2
  fi
}

cmd="${1:-up}"
shift || true

case "$cmd" in
  up)
    warn_resources
    exec "${COMPOSE[@]}" up "${SERVICES[@]}" "$@"
    ;;
  down)
    exec "${COMPOSE[@]}" down "$@"
    ;;
  ps)
    exec "${COMPOSE[@]}" ps "$@"
    ;;
  logs)
    exec "${COMPOSE[@]}" logs -f "$@"
    ;;
  config)
    exec "${COMPOSE[@]}" config "$@"
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    echo "Usage: $0 {up|down|ps|logs|config} [args...]" >&2
    exit 1
    ;;
esac
