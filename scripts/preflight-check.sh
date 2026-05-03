#!/usr/bin/env bash
# ============================================================================
# memdog pre-flight resource check
#
# Usage:
#   ./scripts/preflight-check.sh              # Check local Docker Compose
#   ./scripts/preflight-check.sh --gke        # Check GKE cluster resources
#   ./scripts/preflight-check.sh --profile minimal   # Check for a specific profile
#
# Profiles:
#   minimal  — API + UI + Postgres only (no AI, no pipeline)
#   standard — Full stack minus Ollama large + Neo4j
#   full     — Everything including all Ollama tiers + Neo4j + Nango
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

MODE="local"
PROFILE="full"

while [[ $# -gt 0 ]]; do
  case $1 in
    --gke) MODE="gke"; shift ;;
    --profile) PROFILE="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ============================================================================
# Resource definitions (requests / limits) per component
# Format: name:req_cpu_m:req_mem_mb:lim_cpu_m:lim_mem_mb:profile
# ============================================================================

COMPONENTS=(
  # Core
  "API:100:256:1000:1024:minimal"
  "UI (Cloud Run):100:256:500:512:minimal"
  "PostgreSQL+pgvector:250:512:1000:1024:minimal"

  # Standard adds
  "Webhook Gateway:100:128:500:256:standard"
  "Webhook Agent:50:128:500:512:standard"
  "Webhook Receiver:25:64:200:256:standard"
  "Webhook Pull Worker:25:64:200:256:standard"
  "NATS:25:64:200:128:standard"
  "Redis:50:64:200:128:standard"
  "MCP Server:100:128:500:256:standard"
  "Supabase Auth:100:128:500:256:standard"
  "Supabase Kong:100:128:500:256:standard"
  "Supabase PostgREST:100:128:500:256:standard"
  "Supabase Realtime:100:128:500:256:standard"
  "Supabase Meta:50:64:250:128:standard"
  "Supabase Studio:100:256:500:512:standard"

  # Full adds
  "Ollama Embedding:50:768:500:2048:full"
  "Ollama Chat (4b):100:1024:2000:4096:full"
  "Ollama Large (27b):200:2048:4000:8192:full"
  "Neo4j:250:512:500:1024:full"
  "OpenClaw Node:50:512:2000:4096:full"
  "Nango Server:100:256:500:512:full"
  "Nango Postgres:100:256:500:512:full"
)

# Profile hierarchy: minimal < standard < full
profile_includes() {
  local comp_profile="$1"
  case "$PROFILE" in
    full) return 0 ;;
    standard) [[ "$comp_profile" != "full" ]] && return 0 || return 1 ;;
    minimal) [[ "$comp_profile" == "minimal" ]] && return 0 || return 1 ;;
  esac
}

# ============================================================================
# Display resource matrix
# ============================================================================

echo -e "\n${BOLD}${BLUE}========================================${NC}"
echo -e "${BOLD}${BLUE}  memdog Resource Matrix${NC}"
echo -e "${BOLD}${BLUE}========================================${NC}"
echo -e "\n${BOLD}Profile: ${GREEN}${PROFILE}${NC}  |  Mode: ${GREEN}${MODE}${NC}\n"

printf "  ${BOLD}%-25s %8s %8s %8s %8s  %s${NC}\n" "Component" "Req CPU" "Req Mem" "Lim CPU" "Lim Mem" "Tier"
printf "  %-25s %8s %8s %8s %8s  %s\n" "-------------------------" "--------" "--------" "--------" "--------" "--------"

total_req_cpu=0
total_req_mem=0
total_lim_cpu=0
total_lim_mem=0
count=0

for comp in "${COMPONENTS[@]}"; do
  IFS=':' read -r name req_cpu req_mem lim_cpu lim_mem tier <<< "$comp"
  if profile_includes "$tier"; then
    printf "  %-25s %6sm %6sMi %6sm %6sMi  %s\n" "$name" "$req_cpu" "$req_mem" "$lim_cpu" "$lim_mem" "$tier"
    total_req_cpu=$((total_req_cpu + req_cpu))
    total_req_mem=$((total_req_mem + req_mem))
    total_lim_cpu=$((total_lim_cpu + lim_cpu))
    total_lim_mem=$((total_lim_mem + lim_mem))
    count=$((count + 1))
  fi
done

echo ""
printf "  ${BOLD}%-25s %6sm %6sMi %6sm %6sMi${NC}\n" "TOTAL ($count components)" "$total_req_cpu" "$total_req_mem" "$total_lim_cpu" "$total_lim_mem"

# Convert to human-readable
req_cpu_cores=$(echo "scale=1; $total_req_cpu / 1000" | bc)
req_mem_gb=$(echo "scale=1; $total_req_mem / 1024" | bc)
lim_cpu_cores=$(echo "scale=1; $total_lim_cpu / 1000" | bc)
lim_mem_gb=$(echo "scale=1; $total_lim_mem / 1024" | bc)

echo ""
echo -e "  ${BOLD}Summary:${NC}"
echo -e "    Requests (guaranteed):  ${GREEN}${req_cpu_cores} CPU cores${NC},  ${GREEN}${req_mem_gb} GB RAM${NC}"
echo -e "    Limits (burst max):     ${YELLOW}${lim_cpu_cores} CPU cores${NC},  ${YELLOW}${lim_mem_gb} GB RAM${NC}"
echo ""

# ============================================================================
# Check available resources
# ============================================================================

echo -e "${BOLD}${BLUE}========================================${NC}"
echo -e "${BOLD}${BLUE}  Checking Available Resources${NC}"
echo -e "${BOLD}${BLUE}========================================${NC}\n"

if [[ "$MODE" == "local" ]]; then
  # Check local machine
  if [[ "$(uname)" == "Darwin" ]]; then
    hw_cpu=$(sysctl -n hw.ncpu 2>/dev/null || echo "?")
    hw_mem_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
    hw_mem_gb=$(echo "scale=1; $hw_mem_bytes / 1073741824" | bc 2>/dev/null || echo "?")
    hw_chip=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "unknown")
  else
    hw_cpu=$(nproc 2>/dev/null || echo "?")
    hw_mem_gb=$(free -g 2>/dev/null | awk '/Mem:/{print $2}' || echo "?")
    hw_chip=$(cat /proc/cpuinfo 2>/dev/null | grep "model name" | head -1 | cut -d: -f2 | xargs || echo "unknown")
  fi

  echo -e "  ${BOLD}Hardware:${NC} $hw_chip"
  echo -e "  ${BOLD}CPU cores:${NC} $hw_cpu"
  echo -e "  ${BOLD}RAM:${NC} ${hw_mem_gb} GB"
  echo ""

  # Docker resources
  if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    docker_cpus=$(docker info 2>/dev/null | grep "CPUs:" | awk '{print $2}')
    docker_mem=$(docker info 2>/dev/null | grep "Total Memory:" | awk '{print $3, $4}')
    echo -e "  ${BOLD}Docker CPUs:${NC} ${docker_cpus:-unknown}"
    echo -e "  ${BOLD}Docker Memory:${NC} ${docker_mem:-unknown}"
    echo ""

    # Disk
    docker_root=$(docker info 2>/dev/null | grep "Docker Root Dir" | awk '{print $NF}' || true)
    if [[ -n "$docker_root" ]] && [[ -d "$docker_root" ]]; then
      disk_avail=$(df -h "$docker_root" 2>/dev/null | tail -1 | awk '{print $4}' || true)
      echo -e "  ${BOLD}Docker disk available:${NC} ${disk_avail:-unknown}"
    fi
  else
    echo -e "  ${RED}Docker not running${NC}"
  fi

  echo ""

  # Verdict
  if [[ "$hw_mem_gb" != "?" ]]; then
    mem_int=${hw_mem_gb%.*}
    if (( mem_int >= 32 )); then
      echo -e "  ${GREEN}RAM is sufficient for '${PROFILE}' profile${NC}"
    elif (( mem_int >= 16 )); then
      if [[ "$PROFILE" == "full" ]]; then
        echo -e "  ${YELLOW}16 GB RAM — 'full' profile may be tight. Consider 'standard' profile${NC}"
      else
        echo -e "  ${GREEN}RAM is sufficient for '${PROFILE}' profile${NC}"
      fi
    elif (( mem_int >= 8 )); then
      if [[ "$PROFILE" == "minimal" ]]; then
        echo -e "  ${GREEN}RAM is sufficient for 'minimal' profile${NC}"
      else
        echo -e "  ${RED}8 GB RAM — only 'minimal' profile recommended${NC}"
      fi
    else
      echo -e "  ${RED}Less than 8 GB RAM — memdog may not run well${NC}"
    fi
  fi

else
  # GKE mode — check cluster resources
  GKE_CONTEXT="${GKE_CONTEXT:-gke_memdog-dev_us-central1-a_open-jaw}"

  if ! kubectl cluster-info --context "$GKE_CONTEXT" &>/dev/null 2>&1; then
    echo -e "  ${RED}Cannot connect to GKE cluster. Run:${NC}"
    echo "    gcloud container clusters get-credentials open-jaw --zone us-central1-a --project memdog-dev"
    exit 1
  fi

  echo -e "  ${BOLD}GKE Cluster Nodes:${NC}\n"
  printf "  ${BOLD}%-45s %8s %10s %12s${NC}\n" "Node" "CPU" "Memory" "Pool"
  printf "  %-45s %8s %10s %12s\n" "---------------------------------------------" "--------" "----------" "------------"

  total_node_cpu=0
  total_node_mem=0

  while IFS= read -r line; do
    node_name=$(echo "$line" | awk '{print $1}')
    node_cpu=$(kubectl describe node "$node_name" --context "$GKE_CONTEXT" 2>/dev/null | grep -A 5 "Allocatable:" | grep "cpu:" | awk '{print $2}')
    node_mem=$(kubectl describe node "$node_name" --context "$GKE_CONTEXT" 2>/dev/null | grep -A 5 "Allocatable:" | grep "memory:" | awk '{print $2}')
    node_pool=$(kubectl get node "$node_name" --context "$GKE_CONTEXT" -o jsonpath='{.metadata.labels.cloud\.google\.com/gke-nodepool}' 2>/dev/null)

    # Convert cpu to millicores
    if [[ "$node_cpu" =~ ^[0-9]+$ ]]; then
      cpu_m=$((node_cpu * 1000))
    elif [[ "$node_cpu" =~ ^[0-9]+m$ ]]; then
      cpu_m=${node_cpu%m}
    else
      cpu_m=0
    fi

    # Convert memory to Mi
    if [[ "$node_mem" =~ Ki$ ]]; then
      mem_mi=$(( ${node_mem%Ki} / 1024 ))
    elif [[ "$node_mem" =~ Mi$ ]]; then
      mem_mi=${node_mem%Mi}
    elif [[ "$node_mem" =~ Gi$ ]]; then
      mem_mi=$(( ${node_mem%Gi} * 1024 ))
    else
      mem_mi=0
    fi

    total_node_cpu=$((total_node_cpu + cpu_m))
    total_node_mem=$((total_node_mem + mem_mi))

    printf "  %-45s %6sm %8sMi %12s\n" "$node_name" "$cpu_m" "$mem_mi" "${node_pool:-default}"
  done < <(kubectl get nodes --context "$GKE_CONTEXT" --no-headers 2>/dev/null | awk '{print $1}')

  echo ""
  total_node_cpu_cores=$(echo "scale=1; $total_node_cpu / 1000" | bc)
  total_node_mem_gb=$(echo "scale=1; $total_node_mem / 1024" | bc)
  printf "  ${BOLD}%-45s %6sm %8sMi${NC}\n" "TOTAL ALLOCATABLE" "$total_node_cpu" "$total_node_mem"
  echo -e "  (${total_node_cpu_cores} cores, ${total_node_mem_gb} GB)\n"

  # Compare
  echo -e "  ${BOLD}Fit Analysis (${PROFILE} profile):${NC}"
  cpu_pct=$(echo "scale=0; $total_req_cpu * 100 / $total_node_cpu" | bc 2>/dev/null || echo "?")
  mem_pct=$(echo "scale=0; $total_req_mem * 100 / $total_node_mem" | bc 2>/dev/null || echo "?")

  echo -e "    CPU requests:  ${total_req_cpu}m / ${total_node_cpu}m  (${cpu_pct}%)"
  echo -e "    Memory requests: ${total_req_mem}Mi / ${total_node_mem}Mi  (${mem_pct}%)"
  echo ""

  if [[ "$cpu_pct" != "?" ]] && [[ "$mem_pct" != "?" ]]; then
    if (( cpu_pct < 70 && mem_pct < 70 )); then
      echo -e "  ${GREEN}Cluster has headroom for '${PROFILE}' profile${NC}"
    elif (( cpu_pct < 90 && mem_pct < 90 )); then
      echo -e "  ${YELLOW}Cluster is tight — '${PROFILE}' will fit but little room to burst${NC}"
    else
      echo -e "  ${RED}Cluster may not fit '${PROFILE}' profile — consider scaling nodes or using a smaller profile${NC}"
    fi
  fi

  # Show current usage
  echo ""
  echo -e "  ${BOLD}Current Pod Resource Usage:${NC}\n"
  for ns in memdog webhook-pipeline webhook-gateway supabase nango; do
    pod_count=$(kubectl get pods -n "$ns" --context "$GKE_CONTEXT" --no-headers 2>/dev/null | grep -c Running || true)
    if (( pod_count > 0 )); then
      echo -e "    ${BOLD}${ns}${NC}: ${pod_count} running pods"
    else
      echo -e "    ${ns}: ${YELLOW}no running pods${NC}"
    fi
  done
fi

echo ""
echo -e "${BOLD}${BLUE}========================================${NC}"
echo -e "${BOLD}${BLUE}  Profile Comparison${NC}"
echo -e "${BOLD}${BLUE}========================================${NC}\n"

cat << 'TABLE'
  Profile     Components   Min RAM   Min CPU   Best for
  ----------  ----------   -------   -------   --------
  minimal      3 pods       4 GB     2 cores   Dev/testing, no AI
  standard    16 pods      12 GB     4 cores   Full stack, cloud LLMs (Gemini)
  full        23 pods      24 GB     8 cores   Everything + local Ollama models

  Ollama model VRAM/RAM requirements (additional):
  Model            RAM needed   Disk
  ---------------  ----------   ------
  embeddinggemma     1 GB       1.6 GB
  gemma3:4b          4 GB       3.3 GB
  gemma3:12b         8 GB       8.1 GB
  gemma3:27b        16 GB      17.0 GB
  qwen3-vl           4 GB       5.5 GB
TABLE

echo ""
echo -e "Run with ${BOLD}--profile minimal|standard|full${NC} to see specific requirements."
echo -e "Run with ${BOLD}--gke${NC} to check your GKE cluster capacity.\n"
