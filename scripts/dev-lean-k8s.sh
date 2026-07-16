#!/usr/bin/env bash
# Lean local Kubernetes stack for Docker Desktop.
#
# Profiles:
#   core (default) — postgres, redis, neo4j, api, ui, mcp, gateway,
#                    HTTP ADK processor. Fits ~10 GB Docker Desktop memory.
#   full           — core base + NATS webhook pipeline (receiver/pull-worker/agent)
#                    + Nango + Supabase (incl. Studio/Meta/Realtime/seed) + OpenClaw.
#                    Prefer 12–16 GB Docker Desktop memory.
#
# No in-cluster Ollama — uses host Metal Ollama at http://host.docker.internal:11434.
#
# Usage:
#   ./scripts/dev-lean-k8s.sh up [core|full] [--no-build] [--no-forward]
#   ./scripts/dev-lean-k8s.sh down [core|full|all]
#   ./scripts/dev-lean-k8s.sh status
#   ./scripts/dev-lean-k8s.sh logs [deployment]
#   ./scripts/dev-lean-k8s.sh forward [core|full]
#   ./scripts/dev-lean-k8s.sh forward-dev [core|full]   # API/services only (no UI :3000)
#   ./scripts/dev-lean-k8s-ui-dev.sh [core|full] [--no-build]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

K8S_LEAN_CORE="$ROOT/k8s/lean/core"
K8S_LEAN_FULL="$ROOT/k8s/lean/full"
PID_FILE="$ROOT/.dev-lean-k8s-pids"
PROFILE_FILE="$ROOT/.dev-lean-k8s-profile"
KUSTOMIZE_FLAGS=(--load-restrictor LoadRestrictionsNone)

HOST_OLLAMA_URL="${OLLAMA_LOCAL_API_BASE:-http://host.docker.internal:11434}"

lean_dir_for() {
  case "$1" in
    core) echo "$K8S_LEAN_CORE" ;;
    full) echo "$K8S_LEAN_FULL" ;;
    *) echo "Unknown profile: $1 (use core|full)" >&2; return 1 ;;
  esac
}

save_profile() {
  echo "$1" > "$PROFILE_FILE"
}

load_profile() {
  if [[ -f "$PROFILE_FILE" ]]; then
    cat "$PROFILE_FILE"
  else
    echo "core"
  fi
}

kubectl_lean_apply() {
  local profile="$1"
  local dir
  dir="$(lean_dir_for "$profile")"
  if [[ "$profile" == "full" ]]; then
    # Jobs are immutable — allow re-seed on each full up
    kubectl -n supabase delete job supabase-seed --ignore-not-found 2>/dev/null || true
  fi
  kubectl kustomize "$dir" "${KUSTOMIZE_FLAGS[@]}" | kubectl apply -f -
  save_profile "$profile"
}

kubectl_lean_delete() {
  local profile="$1"
  local dir
  dir="$(lean_dir_for "$profile")"
  kubectl kustomize "$dir" "${KUSTOMIZE_FLAGS[@]}" | kubectl delete -f - --ignore-not-found || true
}

force_ns_finalize() {
  local ns="$1"
  if kubectl get ns "$ns" >/dev/null 2>&1; then
    kubectl get ns "$ns" -o json 2>/dev/null | python3 -c '
import json,sys
ns=json.load(sys.stdin)
ns["spec"]["finalizers"]=[]
json.dump(ns, sys.stdout)
' 2>/dev/null | kubectl replace --raw "/api/v1/namespaces/${ns}/finalize" -f - >/dev/null 2>&1 || true
  fi
}

# When switching full → core, remove addon workloads so they don't keep using RAM.
prune_addons() {
  echo "==> Pruning full-profile addons (NATS pipeline, nango, supabase, openclaw)..."
  kubectl -n webhook-pipeline delete deploy nats webhook-receiver webhook-pull-worker webhook-agent \
    --ignore-not-found 2>/dev/null || true
  kubectl -n webhook-pipeline delete svc nats webhook-receiver webhook-agent --ignore-not-found 2>/dev/null || true
  kubectl -n webhook-pipeline delete cm webhook-pipeline-config --ignore-not-found 2>/dev/null || true
  kubectl -n webhook-pipeline delete secret webhook-pipeline-secrets --ignore-not-found 2>/dev/null || true
  kubectl -n webhook-pipeline delete sa webhook-pipeline-sa --ignore-not-found 2>/dev/null || true
  # Restore HTTP processor if it was scaled to 0 by full
  kubectl -n webhook-pipeline scale deploy/webhook-processor --replicas=1 --ignore-not-found 2>/dev/null || true

  kubectl delete deploy openclaw-node -n webhook-gateway --ignore-not-found 2>/dev/null || true
  kubectl delete svc openclaw-node -n webhook-gateway --ignore-not-found 2>/dev/null || true
  kubectl delete pvc openclaw-home -n webhook-gateway --ignore-not-found 2>/dev/null || true
  kubectl delete cm,secret -n webhook-gateway -l app.kubernetes.io/component=openclaw-node --ignore-not-found 2>/dev/null || true
  kubectl -n mem-dog delete secret api-supabase-secrets --ignore-not-found 2>/dev/null || true
  kubectl delete ns nango supabase --ignore-not-found --wait=false 2>/dev/null || true
  force_ns_finalize nango
  force_ns_finalize supabase
}

warn_resources() {
  local profile="$1"
  local ctx
  ctx="$(kubectl config current-context 2>/dev/null || echo "")"
  if [[ "$ctx" != "docker-desktop" ]]; then
    echo "WARN: kubectl context is '${ctx:-<none>}', expected 'docker-desktop'." >&2
  fi

  local mem_mib=""
  local settings="$HOME/Library/Group Containers/group.com.docker/settings-store.json"
  if [[ -f "$settings" ]]; then
    mem_mib="$(python3 -c "import json; print(json.load(open('$settings')).get('MemoryMiB',''))" 2>/dev/null || true)"
  fi
  if [[ "$profile" == "full" && -n "$mem_mib" && "$mem_mib" -lt 12288 ]]; then
    echo "WARN: Docker Desktop MemoryMiB=${mem_mib} (< 12288). Prefer 12–16 GB for profile=full." >&2
  elif [[ "$profile" == "core" && -n "$mem_mib" && "$mem_mib" -lt 8192 ]]; then
    echo "WARN: Docker Desktop MemoryMiB=${mem_mib} (< 8192). Prefer ≥8–10 GB for profile=core." >&2
  fi

  if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    echo "WARN: Host Ollama not responding on :11434." >&2
    echo "      Start Ollama on the Mac (Metal) or set cloud keys in api/.env." >&2
  fi
}

load_api_env() {
  local env_file="$ROOT/api/.env"
  [[ -f "$env_file" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
}

ensure_local_images() {
  local profile="${1:-core}"
  local pairs=(
    "mem-dog-api:local|mem-dog-api:latest"
    "mem-dog-ui:local|mem-dog-ui:latest"
    "mcp-server:local|mem-dog-mcp-server:latest"
    "webhook-gateway:local|mem-dog-webhook-gateway:latest"
    "webhook-processor:local|mem-dog-webhook-processor:latest"
  )
  if [[ "$profile" == "full" ]]; then
    pairs+=(
      "webhook-agent:local|webhook-processor:local"
      "webhook-receiver:local|"
      "webhook-pull-worker:local|"
    )
  fi
  local missing=0
  for pair in "${pairs[@]}"; do
    local want="${pair%%|*}" alt="${pair##*|}"
    if docker image inspect "$want" >/dev/null 2>&1; then
      continue
    fi
    if [[ -n "$alt" ]] && docker image inspect "$alt" >/dev/null 2>&1; then
      echo "==> Tagging $alt -> $want"
      docker tag "$alt" "$want"
      continue
    fi
    echo "WARN: missing image $want${alt:+ (and $alt)}" >&2
    missing=1
  done
  return "$missing"
}

build_images() {
  local profile="${1:-core}"
  echo "==> Building local images (profile=${profile})..."
  docker build -t mem-dog-api:local "$ROOT/api"
  # Must match k8s/lean/api-auth-secret.yaml (API rejects unauthenticated calls).
  # Unique tag so Kubernetes picks up rebuilds (IfNotPresent + :local stays stale).
  local ui_api_key="${NEXT_PUBLIC_API_KEY:-${API_KEY:-dev-local-key}}"
  local ui_tag="local-$(date +%Y%m%d%H%M%S)"
  docker build -t "mem-dog-ui:${ui_tag}" -t mem-dog-ui:local "$ROOT/ui" \
    --build-arg "NEXT_PUBLIC_API_URL=http://localhost:8080" \
    --build-arg "NEXT_PUBLIC_API_KEY=${ui_api_key}" \
    --build-arg "NEXT_PUBLIC_WEBHOOK_GATEWAY_URL=${NEXT_PUBLIC_WEBHOOK_GATEWAY_URL:-http://localhost:8070}" \
    --build-arg "NEXT_PUBLIC_WEBHOOK_API_KEY=${NEXT_PUBLIC_WEBHOOK_API_KEY:-${WGW_API_KEY:-}}" \
    --build-arg "API_URL=http://api.mem-dog.svc.cluster.local:8080"
  echo "$ui_tag" > "$ROOT/.dev-lean-k8s-ui-tag"
  docker build -t mcp-server:local -f "$ROOT/mcp-server/Dockerfile" "$ROOT"
  docker build -t webhook-gateway:local "$ROOT/webhook-gateway"
  local docling_arg="${INSTALL_DOCLING:-false}"
  docker build -t webhook-processor:local \
    --build-arg "INSTALL_DOCLING=${docling_arg}" \
    "$ROOT/webhook/processor"
  if [[ "$profile" == "full" ]]; then
    docker build -t webhook-agent:local \
      --build-arg "INSTALL_DOCLING=${docling_arg}" \
      "$ROOT/webhook/processor"
    docker build -t webhook-receiver:local -f "$ROOT/webhook/receiver/Dockerfile.gke" "$ROOT/webhook/receiver"
    docker build -t webhook-pull-worker:local -f "$ROOT/webhook/processor/Dockerfile.pull-worker" "$ROOT/webhook/processor"
  fi
  echo "==> Images built (ui tag=${ui_tag})."
}

apply_stack() {
  local profile="$1"
  echo "==> Applying lean Kubernetes manifests (profile=${profile})..."
  if [[ "$profile" == "core" ]]; then
    prune_addons
  fi
  kubectl_lean_apply "$profile"

  load_api_env
  if [[ -n "${SYSTEM_GEMINI_API_KEY:-${GEMINI_API_KEY:-}}" ]]; then
    local gw_args=(
      --from-literal=GEMINI_API_KEY="${SYSTEM_GEMINI_API_KEY:-${GEMINI_API_KEY:-}}"
      --from-literal=WEBHOOK_API_KEY="${WEBHOOK_API_KEY:-dev-key}"
      --from-literal=WGW_API_KEY="${WGW_API_KEY:-}"
    )
    if [[ "$profile" == "full" ]]; then
      gw_args+=(--from-literal=NANGO_SECRET_KEY="${NANGO_SECRET_KEY:-ncLyB5dUqjsoDzw6DHKeYj5CENL4I4C8SOcL8yMJp1U=}")
    fi
    kubectl -n webhook-gateway create secret generic webhook-gateway-secrets \
      "${gw_args[@]}" --dry-run=client -o yaml | kubectl apply -f -
    if [[ "$profile" == "full" ]]; then
      kubectl -n webhook-gateway create secret generic openclaw-node-secrets \
        --from-literal=GEMINI_API_KEY="${SYSTEM_GEMINI_API_KEY:-${GEMINI_API_KEY:-}}" \
        --from-literal=OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-lean-openclaw-token}" \
        --from-literal=MEM_DOG_API_KEY="${MEM_DOG_API_KEY:-${API_KEY:-dev-local-key}}" \
        --dry-run=client -o yaml | kubectl apply -f -
      # Wire pipeline secrets from api/.env when present
      kubectl -n webhook-pipeline create secret generic webhook-pipeline-secrets \
        --from-literal=GOOGLE_API_KEY="${SYSTEM_GEMINI_API_KEY:-${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}}" \
        --from-literal=MEM_DOG_API_KEY="${MEM_DOG_API_KEY:-${API_KEY:-dev-local-key}}" \
        --from-literal=OLLAMA_CLOUD_API_KEY="${OLLAMA_CLOUD_API_KEY:-${OLLAMA_API_KEY:-}}" \
        --dry-run=client -o yaml | kubectl apply -f -
    fi
  fi

  echo "==> Waiting for core deployments..."
  kubectl -n data wait --for=condition=available deployment/postgres --timeout=180s
  kubectl -n data wait --for=condition=available deployment/redis --timeout=120s
  kubectl -n neo4j wait --for=condition=available deployment/neo4j --timeout=300s || true

  if [[ "$profile" == "full" ]]; then
    echo "==> Waiting for NATS pipeline / Supabase / Nango..."
    kubectl -n webhook-pipeline wait --for=condition=available deployment/nats --timeout=120s || true
    kubectl -n webhook-pipeline wait --for=condition=available deployment/webhook-receiver --timeout=180s || true
    kubectl -n webhook-pipeline wait --for=condition=available deployment/webhook-agent --timeout=300s || true
    kubectl -n webhook-pipeline wait --for=condition=available deployment/webhook-pull-worker --timeout=180s || true
    kubectl -n supabase wait --for=condition=ready pod -l app.kubernetes.io/name=supabase-db --timeout=300s || true
    kubectl -n supabase wait --for=condition=available deployment/supabase-kong --timeout=180s || true
    kubectl -n supabase wait --for=condition=available deployment/supabase-auth --timeout=180s || true
    kubectl -n supabase wait --for=condition=available deployment/supabase-rest --timeout=180s || true
    kubectl -n supabase wait --for=condition=available deployment/supabase-meta --timeout=120s || true
    kubectl -n supabase wait --for=condition=available deployment/supabase-realtime --timeout=180s || true
    kubectl -n supabase wait --for=condition=available deployment/supabase-studio --timeout=180s || true
    echo "==> Waiting for supabase-seed..."
    if ! kubectl -n supabase wait --for=condition=complete job/supabase-seed --timeout=180s 2>/dev/null; then
      echo "==> Re-running supabase-seed..."
      kubectl -n supabase delete job supabase-seed --ignore-not-found
      kubectl apply -f "$ROOT/k8s/lean/supabase-seed-job.yaml"
      kubectl -n supabase wait --for=condition=complete job/supabase-seed --timeout=180s || true
    fi
    kubectl -n nango wait --for=condition=ready pod -l app=nango-db --timeout=300s || true
    kubectl -n nango wait --for=condition=available deployment/nango-server --timeout=180s || true
  fi

  echo "==> Waiting for app deployments..."
  kubectl -n mem-dog wait --for=condition=available deployment/api --timeout=300s || true
  kubectl -n mem-dog wait --for=condition=available deployment/ui --timeout=180s || true
  kubectl -n mem-dog wait --for=condition=available deployment/mcp-server --timeout=120s || true
  kubectl -n webhook-gateway wait --for=condition=available deployment/webhook-gateway --timeout=180s || true
  if [[ "$profile" == "core" ]]; then
    kubectl -n webhook-pipeline wait --for=condition=available deployment/webhook-processor --timeout=300s || true
  fi
  if [[ "$profile" == "full" ]]; then
    kubectl -n webhook-gateway wait --for=condition=available deployment/openclaw-node --timeout=180s || true
  fi

  # envFrom ConfigMaps/Secrets don't reload in-place — bounce gateway (and API on full)
  # so WEBHOOK_GATEWAY_URL / NANGO_* / pipeline secrets take effect.
  echo "==> Rolling gateway to pick up ConfigMap/Secret env..."
  kubectl -n webhook-gateway rollout restart deployment/webhook-gateway
  kubectl -n webhook-gateway rollout status deployment/webhook-gateway --timeout=180s || true
  if [[ "$profile" == "full" ]]; then
    kubectl -n mem-dog rollout restart deployment/api
    kubectl -n mem-dog rollout status deployment/api --timeout=180s || true
  fi

  # Point UI at freshly built unique tag (avoids stale :local with imagePullPolicy IfNotPresent).
  if [[ -f "$ROOT/.dev-lean-k8s-ui-tag" ]]; then
    local ui_tag
    ui_tag="$(cat "$ROOT/.dev-lean-k8s-ui-tag")"
    if docker image inspect "mem-dog-ui:${ui_tag}" >/dev/null 2>&1; then
      echo "==> Pinning UI deployment to mem-dog-ui:${ui_tag}..."
      kubectl -n mem-dog set image deployment/ui "ui=mem-dog-ui:${ui_tag}"
      kubectl -n mem-dog rollout status deployment/ui --timeout=180s || true
    fi
  fi

  echo "==> Stack applied (profile=${profile})."
}

stop_forwards() {
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
}

start_forwards_dev() {
  local profile="${1:-$(load_profile)}"
  stop_forwards
  : > "$PID_FILE"

  forward() {
    local ns="$1" svc="$2" local_port="$3" remote_port="${4:-$3}"
    kubectl -n "$ns" port-forward "svc/$svc" "${local_port}:${remote_port}" \
      >/dev/null 2>&1 &
    echo "$!" >> "$PID_FILE"
  }

  forward mem-dog api 8080 8080
  forward webhook-gateway webhook-gateway 8070 8080
  forward mem-dog mcp-server 8091 8080
  forward neo4j neo4j 7474 7474

  echo "==> Port-forwards (background, dev UI mode) profile=${profile}:"
  echo "    Local UI    http://localhost:${UI_DEV_PORT:-3001} (npm run dev)"
  echo "    API         http://localhost:8080"
  echo "    Gateway     http://localhost:8070"
  echo "    MCP SSE     http://localhost:8091/mcp/sse"
  echo "    Neo4j       http://localhost:7474"

  if [[ "$profile" == "full" ]]; then
    forward webhook-pipeline webhook-agent 8090 8080
    forward webhook-pipeline webhook-receiver 8092 8080
    forward nango nango-server 3003 3003
    forward supabase supabase-kong 8000 8000
    forward supabase supabase-studio 54323 3000
    forward webhook-gateway openclaw-node 18789 18789
    echo "    ADK agent   http://localhost:8090"
    echo "    Receiver    http://localhost:8092"
    echo "    Nango       http://localhost:3003"
    echo "    Supabase    http://localhost:8000"
    echo "    Studio      http://localhost:54323"
    echo "    OpenClaw    http://localhost:18789"
  else
    forward webhook-pipeline webhook-processor 8090 8080
    echo "    ADK agent   http://localhost:8090"
  fi
  echo "    Host Ollama ${HOST_OLLAMA_URL}"
}

start_forwards() {
  local profile="${1:-$(load_profile)}"
  stop_forwards
  : > "$PID_FILE"

  forward() {
    local ns="$1" svc="$2" local_port="$3" remote_port="${4:-$3}"
    kubectl -n "$ns" port-forward "svc/$svc" "${local_port}:${remote_port}" \
      >/dev/null 2>&1 &
    echo "$!" >> "$PID_FILE"
  }

  forward mem-dog ui 3000 3000
  forward mem-dog api 8080 8080
  forward webhook-gateway webhook-gateway 8070 8080
  forward mem-dog mcp-server 8091 8080
  forward neo4j neo4j 7474 7474

  echo "==> Port-forwards (background) profile=${profile}:"
  echo "    UI          http://localhost:3000"
  echo "    API         http://localhost:8080"
  echo "    Gateway     http://localhost:8070"
  echo "    MCP SSE     http://localhost:8091/mcp/sse"
  echo "    Neo4j       http://localhost:7474"

  if [[ "$profile" == "full" ]]; then
    forward webhook-pipeline webhook-agent 8090 8080
    forward webhook-pipeline webhook-receiver 8092 8080
    forward nango nango-server 3003 3003
    forward supabase supabase-kong 8000 8000
    forward supabase supabase-studio 54323 3000
    forward webhook-gateway openclaw-node 18789 18789
    echo "    ADK agent   http://localhost:8090"
    echo "    Receiver    http://localhost:8092"
    echo "    Nango       http://localhost:3003"
    echo "    Supabase    http://localhost:8000"
    echo "    Studio      http://localhost:54323"
    echo "    OpenClaw    http://localhost:18789"
  else
    forward webhook-pipeline webhook-processor 8090 8080
    echo "    ADK agent   http://localhost:8090"
  fi
  echo "    Host Ollama ${HOST_OLLAMA_URL}"
}

print_status() {
  local profile
  profile="$(load_profile)"
  echo "profile: ${profile}"
  kubectl get pods -A | grep -E 'mem-dog|neo4j|webhook|data|nango|supabase' || true
}

parse_profile_and_flags() {
  PROFILE="core"
  NO_BUILD=0
  NO_FORWARD=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      core|full) PROFILE="$1"; shift ;;
      --no-build) NO_BUILD=1; shift ;;
      --no-forward) NO_FORWARD=1; shift ;;
      *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
  done
}

cmd="${1:-up}"
shift || true

case "$cmd" in
  up)
    parse_profile_and_flags "$@"
    warn_resources "$PROFILE"
    if [[ "$NO_BUILD" -eq 0 ]]; then
      build_images "$PROFILE"
    else
      if ! ensure_local_images "$PROFILE"; then
        echo "ERROR: lean :local images missing. Re-run without --no-build." >&2
        exit 1
      fi
    fi
    apply_stack "$PROFILE"
    if [[ "$NO_FORWARD" -eq 0 ]]; then
      start_forwards "$PROFILE"
    fi
    print_status
    ;;
  down)
    local_profile="${1:-all}"
    stop_forwards
    case "$local_profile" in
      core)
        kubectl_lean_delete core
        ;;
      full)
        kubectl_lean_delete full
        ;;
      all|"")
        kubectl_lean_delete full 2>/dev/null || true
        kubectl_lean_delete core 2>/dev/null || true
        prune_addons
        ;;
      *)
        echo "Usage: $0 down [core|full|all]" >&2
        exit 1
        ;;
    esac
    rm -f "$PROFILE_FILE"
    echo "==> Lean stack removed (${local_profile})."
    ;;
  status)
    print_status
    ;;
  logs)
    if [[ $# -eq 0 ]]; then
      echo "Usage: $0 logs <deployment> [-n namespace]" >&2
      exit 1
    fi
    kubectl logs -f "$@"
    ;;
  forward)
    start_forwards "${1:-$(load_profile)}"
    ;;
  forward-dev)
    start_forwards_dev "${1:-$(load_profile)}"
    ;;
  stop-forwards)
    stop_forwards
    echo "==> Port-forwards stopped."
    ;;
  build)
    build_images "${1:-core}"
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    echo "Usage: $0 {up|down|status|logs|forward|forward-dev|stop-forwards|build} [core|full] [args...]" >&2
    exit 1
    ;;
esac
