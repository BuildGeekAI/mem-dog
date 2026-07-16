#!/usr/bin/env bash
# Lean k8s backend + local Next.js UI (hot reload on :3001).
#
# Usage:
#   ./scripts/dev-lean-k8s-ui-dev.sh [core|full] [--no-build]
#
# Starts lean Kubernetes (no in-cluster UI port-forward), forwards API/services,
# then runs `npm run dev` pointed at http://localhost:8080 with dev-local-key auth.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="core"
NO_BUILD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    core|full) PROFILE="$1"; shift ;;
    --no-build) NO_BUILD=1; shift ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [core|full] [--no-build]" >&2
      exit 1
      ;;
  esac
done

UI_DEV_PORT="${UI_DEV_PORT:-3001}"
export UI_DEV_PORT

if kubectl config get-contexts docker-desktop >/dev/null 2>&1; then
  kubectl config use-context docker-desktop >/dev/null 2>&1 || true
fi

up_args=(up "$PROFILE" --no-forward)
[[ "$NO_BUILD" -eq 1 ]] && up_args+=(--no-build)

echo "==> Starting lean Kubernetes (profile=${PROFILE}, no UI port-forward)..."
"$ROOT/scripts/dev-lean-k8s.sh" "${up_args[@]}"

echo "==> Starting API/service port-forwards (dev UI mode)..."
"$ROOT/scripts/dev-lean-k8s.sh" forward-dev "$PROFILE"

cleanup() {
  echo ""
  echo "==> Stopping port-forwards..."
  "$ROOT/scripts/dev-lean-k8s.sh" stop-forwards
}
trap cleanup EXIT INT TERM

export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8080}"
export NEXT_PUBLIC_API_KEY="${NEXT_PUBLIC_API_KEY:-dev-local-key}"
export NEXT_PUBLIC_WEBHOOK_GATEWAY_URL="${NEXT_PUBLIC_WEBHOOK_GATEWAY_URL:-http://localhost:8070}"
export NEXT_PUBLIC_WEBHOOK_API_KEY="${NEXT_PUBLIC_WEBHOOK_API_KEY:-}"
export API_URL="${API_URL:-http://localhost:8080}"
export API_KEY="${API_KEY:-dev-local-key}"
export CHAT_API_URL="${CHAT_API_URL:-http://localhost:8080}"

echo "==> Starting Next.js dev server on http://localhost:${UI_DEV_PORT}"
echo "    API proxy target: ${API_URL}"
echo "    Press Ctrl+C to stop UI dev server and port-forwards (k8s stack stays up)."

cd "$ROOT/ui"
exec npm run dev -- -p "$UI_DEV_PORT"
