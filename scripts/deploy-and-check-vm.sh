#!/bin/bash
# ==============================================================================
# Deploy VM (Ollama + Docker) and run checks
# ==============================================================================
# Creates GCP VM (optional), runs setup on VM, ensures Docker/Ollama/wrapper
# are running, then runs health and API checks.
#
# Usage:
#   ./scripts/deploy-and-check-vm.sh -p PROJECT_ID -e dev [VM_TYPE]
#   ./scripts/deploy-and-check-vm.sh -p PROJECT_ID -e dev --vm <index_or_label> [--model MODEL]
#   ./scripts/deploy-and-check-vm.sh -p PROJECT_ID -e dev --no-create-vm   # use existing VM
#
# VM_TYPE / --vm: instance index (1-4), instance_type label (e.g. "g2-standard-8 + L4"), or legacy:
#   g2-standard-8 | g2-standard-24 | a2-highgpu-1g | a2-ultragpu-1g (default: a2-highgpu-1g)
# --model: model name from scripts/gcp-vm-options.json (e.g. "Gemma-3-12B"); script passes ollama_tag to setup.
# If --model omitted, uses scripts/.memdog-vm-model (from manual-deploy) or default gemma3:27b.
#
# Examples:
#   ./scripts/deploy-and-check-vm.sh -p myproject -e dev
#   ./scripts/deploy-and-check-vm.sh -p myproject -e dev a2-highgpu-1g
#   ./scripts/deploy-and-check-vm.sh -p myproject -e dev --vm 2 --model "Gemma-3-12B"
#   ./scripts/deploy-and-check-vm.sh -p myproject -e dev --no-create-vm
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() { echo ""; echo -e "${BLUE}======== $1 ========${NC}"; echo ""; }
print_ok() { echo -e "${GREEN}✅ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_err() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
GCP_VM_OPTIONS_JSON="${SCRIPT_DIR}/gcp-vm-options.json"
MEM_DOG_VM_MODEL_FILE="${SCRIPT_DIR}/.memdog-vm-model"
PROJECT_ID=""
ENVIRONMENT="dev"
REGION="us-central1"
VM_TYPE="a2-highgpu-1g"
VM_TYPE_USER=""
VM_MODEL=""
CREATE_VM=true

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project) PROJECT_ID="$2"; shift 2 ;;
        -e|--env)     ENVIRONMENT="$2"; shift 2 ;;
        -r|--region)  REGION="$2"; shift 2 ;;
        --no-create-vm) CREATE_VM=false; shift ;;
        --vm) VM_TYPE_USER="$2"; shift 2 ;;
        --model) VM_MODEL="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 -p PROJECT_ID -e ENV [VM_TYPE|--vm TYPE] [--model MODEL] [--no-create-vm]"
            echo "  VM_TYPE/--vm: 1-4, instance label (e.g. \"g2-standard-8 + L4\"), or g2-standard-8|g2-standard-24|a2-highgpu-1g|a2-ultragpu-1g"
            echo "  --model: model name from gcp-vm-options.json (e.g. Gemma-3-12B); passed to setup as ollama_tag"
            echo "  --no-create-vm: skip VM creation; use existing VM (VM_NAME must exist)"
            exit 0
            ;;
        g2-standard-8|g2-standard-24|a2-highgpu-1g|a2-ultragpu-1g)
            if [[ -z "$VM_TYPE_USER" ]]; then VM_TYPE_USER="$1"; fi
            VM_TYPE="$1"
            shift
            ;;
        *)
            if [[ -z "$VM_TYPE_USER" ]] && [[ "$1" != -* ]]; then
                VM_TYPE_USER="$1"
                VM_TYPE="$1"
                shift
            else
                echo "Unknown option: $1"
                exit 1
            fi
            ;;
    esac
done

# Default VM type when not provided
[[ -z "$VM_TYPE_USER" ]] && VM_TYPE_USER="${VM_TYPE}"
[[ -z "$VM_TYPE" ]] && VM_TYPE="a2-highgpu-1g"

# Resolve VM type from config to GCP machine type (for VM name and manual-deploy)
if [[ -f "$GCP_VM_OPTIONS_JSON" ]] && command -v jq &>/dev/null && [[ -n "$VM_TYPE_USER" ]]; then
    if [[ "$VM_TYPE_USER" =~ ^[1-9][0-9]*$ ]]; then
        count=$(jq '.instances | length' "$GCP_VM_OPTIONS_JSON")
        if (( VM_TYPE_USER >= 1 && VM_TYPE_USER <= count )); then
            VM_TYPE=$(jq -r --argjson i $((VM_TYPE_USER - 1)) '.instances[$i].gcp_machine_type' "$GCP_VM_OPTIONS_JSON")
        fi
    else
        found=$(jq -r --arg t "$VM_TYPE_USER" '
            .instances[] | select(.instance_type == $t or (.instance_type | index($t) != null)) | .gcp_machine_type
        ' "$GCP_VM_OPTIONS_JSON" | head -1)
        if [[ -n "$found" && "$found" != "null" ]]; then
            VM_TYPE="$found"
        elif [[ "$VM_TYPE_USER" == "a2-ultragpu-1g" ]]; then
            VM_TYPE=$(jq -r '.instances[3].gcp_machine_type' "$GCP_VM_OPTIONS_JSON")
        fi
    fi
fi

if [[ -z "$PROJECT_ID" ]]; then
    print_err "Missing -p PROJECT_ID"
    exit 1
fi

VM_NAME="memdog-vm-${VM_TYPE}-${ENVIRONMENT}"
ZONE="${REGION}-a"

# Resolve OLLAMA_MODEL_TAG for setup script: --model (from config), .memdog-vm-model, or default
OLLAMA_MODEL_TAG=""
if [[ -n "$VM_MODEL" ]] && [[ -f "$GCP_VM_OPTIONS_JSON" ]] && command -v jq &>/dev/null; then
    # Find instance index from current VM_TYPE (GCP machine type)
    inst_idx=$(jq -r --arg mt "$VM_TYPE" '
        .instances | to_entries[] | select(.value.gcp_machine_type == $mt) | .key
    ' "$GCP_VM_OPTIONS_JSON" | head -1)
    if [[ -n "$inst_idx" && "$inst_idx" != "null" ]]; then
        OLLAMA_MODEL_TAG=$(jq -r --argjson i "$inst_idx" --arg m "$VM_MODEL" '
            .instances[$i].models[] | select(.model == $m or (.catalog_model_id != null and .catalog_model_id == $m)) | .ollama_tag // empty
        ' "$GCP_VM_OPTIONS_JSON" | head -1)
    fi
fi
if [[ -z "$OLLAMA_MODEL_TAG" ]] && [[ -f "$MEM_DOG_VM_MODEL_FILE" ]]; then
    OLLAMA_MODEL_TAG=$(cat "$MEM_DOG_VM_MODEL_FILE")
fi
[[ -z "$OLLAMA_MODEL_TAG" ]] && OLLAMA_MODEL_TAG="gemma3:27b"

# ------------------------------------------------------------------------------
# 1. Create VM (optional)
# ------------------------------------------------------------------------------
if [[ "$CREATE_VM" == true ]]; then
    print_header "1. Deploy VM: $VM_NAME ($VM_TYPE)"
    if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
        print_warn "VM already exists: $VM_NAME"
    else
        if [[ -n "$VM_MODEL" ]]; then
            "$SCRIPT_DIR/manual-deploy.sh" deploy-vm-instance -p "$PROJECT_ID" -e "$ENVIRONMENT" --vm "$VM_TYPE_USER" --model "$VM_MODEL"
        else
            "$SCRIPT_DIR/manual-deploy.sh" deploy-vm-instance -p "$PROJECT_ID" -e "$ENVIRONMENT" "$VM_TYPE_USER"
        fi
        print_info "Waiting 90s for VM to be SSH-ready..."
        sleep 90
    fi
else
    print_header "1. Using existing VM: $VM_NAME"
    if ! gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
        print_err "VM not found: $VM_NAME in $ZONE"
        exit 1
    fi
fi

EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
if [[ -z "$EXTERNAL_IP" ]]; then
    print_err "Could not get VM external IP"
    exit 1
fi
print_ok "VM IP: $EXTERNAL_IP"

# Ensure firewall allows external access to wrapper (port 8000)
if ! gcloud compute firewall-rules describe memdog-model-server --project="$PROJECT_ID" &>/dev/null; then
    print_info "Creating firewall rule for model server (tcp:8000)..."
    gcloud compute firewall-rules create memdog-model-server \
        --project="$PROJECT_ID" \
        --allow tcp:8000 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=model-server \
        --description="Allow access to Ollama wrapper on port 8000"
    print_ok "Firewall rule created"
fi
# Ensure VM has network tag so the rule applies (required for external access to port 8000)
CURRENT_TAGS=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --format='value(tags.items)' 2>/dev/null || true)
if [[ -z "$CURRENT_TAGS" ]] || ! echo "$CURRENT_TAGS" | tr ',' '\n' | grep -qw "model-server"; then
    print_info "Adding network tag model-server to VM..."
    gcloud compute instances add-tags "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --tags=model-server
    print_ok "Tag added (chat from outside will work after this)"
fi

# ------------------------------------------------------------------------------
# 2. Setup Ollama (Docker + GPU + Model) on VM
# ------------------------------------------------------------------------------
print_header "2. Setup Ollama (Docker + GPU + Model) on VM"

# Copy the complete setup script and the OpenAI wrapper (so step 5 can start port 8000)
gcloud compute scp "$SCRIPT_DIR/setup-ollama-complete.sh" "$VM_NAME:~" --zone="$ZONE" --project="$PROJECT_ID" 2>/dev/null || true
gcloud compute scp --recurse "$SCRIPT_DIR/ollama-openai-wrapper" "$VM_NAME:~" --zone="$ZONE" --project="$PROJECT_ID" 2>/dev/null || true

# Check if already set up
NEED_SETUP=$(gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null" 2>/dev/null || echo "000")

if [[ "$NEED_SETUP" == "200" ]]; then
    print_info "Ollama already up; skipping setup"
else
    print_info "Running complete setup (GPU + Ollama + $OLLAMA_MODEL_TAG)..."
    print_warn "This may take 10-20 minutes (drivers, model download, etc.)"
    
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="
    chmod +x setup-ollama-complete.sh
    OLLAMA_MODEL=$OLLAMA_MODEL_TAG ./setup-ollama-complete.sh
    " || {
        print_warn "Setup failed (see output above). Common causes:"
        print_info "  - Docker permission: SSH to VM and run with sudo: sudo OLLAMA_MODEL=$OLLAMA_MODEL_TAG ./setup-ollama-complete.sh"
        print_info "  - If GPU drivers were just installed: gcloud compute instances reset $VM_NAME --zone=$ZONE then re-run this script"
        exit 1
    }
fi

print_info "Waiting 10s for services..."
sleep 10

# ------------------------------------------------------------------------------
# 3. Checks (on VM via SSH)
# ------------------------------------------------------------------------------
print_header "3. Running checks"

CHECK_FAILED=0

# 3.1 Docker
print_info "Check: Docker daemon"
if gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="sudo systemctl is-active docker" 2>/dev/null | grep -q active; then
    print_ok "Docker is running"
else
    print_err "Docker is not running"
    CHECK_FAILED=1
fi

# 3.2 Ollama container
print_info "Check: Ollama container"
if gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="sudo docker ps --format '{{.Names}}' 2>/dev/null" | grep -q ollama; then
    print_ok "Ollama container is running"
else
    print_warn "Ollama container not running (start with: sudo systemctl start ollama-docker)"
    CHECK_FAILED=1
fi

# 3.3 Wrapper health (from VM localhost)
print_info "Check: Wrapper health (localhost:8000)"
HEALTH=$(gcloud compute ssh "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --command="curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null" 2>/dev/null || echo "000")
if [[ "$HEALTH" == "200" ]]; then
    print_ok "Wrapper health: HTTP $HEALTH"
else
    print_warn "Wrapper health: HTTP $HEALTH (expected 200)"
    CHECK_FAILED=1
fi

# 3.4 Health from outside (your machine)
print_info "Check: Health from outside (http://$EXTERNAL_IP:8000/health)"
EXT_HEALTH=$(curl -s -o /dev/null -w '%{http_code}' "http://$EXTERNAL_IP:8000/health" 2>/dev/null || echo "000")
if [[ "$EXT_HEALTH" == "200" ]]; then
    print_ok "External health: HTTP $EXT_HEALTH"
else
    print_warn "External health: HTTP $EXT_HEALTH (check firewall allows tcp:8000)"
    CHECK_FAILED=1
fi

# 3.5 /v1/models
print_info "Check: GET /v1/models"
MODELS_HTTP=$(curl -s -o /dev/null -w '%{http_code}' "http://$EXTERNAL_IP:8000/v1/models" 2>/dev/null || echo "000")
if [[ "$MODELS_HTTP" == "200" ]]; then
    print_ok "GET /v1/models: HTTP $MODELS_HTTP"
else
    print_warn "GET /v1/models: HTTP $MODELS_HTTP"
fi

# 3.6 Optional: chat (only if a model is available)
MODELS_JSON=$(curl -s "http://$EXTERNAL_IP:8000/v1/models" 2>/dev/null || echo "{}")
FIRST_MODEL=$(echo "$MODELS_JSON" | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"//;s/"//')
if [[ -n "$FIRST_MODEL" ]]; then
    print_info "Check: POST /v1/chat/completions (model: $FIRST_MODEL)"
    CHAT_RESP=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://$EXTERNAL_IP:8000/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"$FIRST_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hi\"}],\"max_tokens\":5}" 2>/dev/null || echo "000")
    if [[ "$CHAT_RESP" == "200" ]]; then
        print_ok "Chat completion: HTTP $CHAT_RESP"
    else
        print_warn "Chat completion: HTTP $CHAT_RESP"
    fi
else
    print_info "No models yet; skip chat check. Pull one: docker exec ollama ollama pull $OLLAMA_MODEL_TAG"
fi

# ------------------------------------------------------------------------------
# 4. Summary
# ------------------------------------------------------------------------------
print_header "4. Summary"

echo "  VM:        $VM_NAME"
echo "  Zone:      $ZONE"
echo "  IP:        $EXTERNAL_IP"
echo "  Health:    http://$EXTERNAL_IP:8000/health"
echo "  Models:    http://$EXTERNAL_IP:8000/v1/models"
echo ""
echo "  Register in API:"
echo "  curl -X POST \"\$API_URL/api/v1/models/vm-instances\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"machine_type\": \"$VM_TYPE\", \"base_url\": \"http://$EXTERNAL_IP:8000\", \"name\": \"Ollama $VM_TYPE\"}'"
echo ""

if [[ $CHECK_FAILED -eq 0 ]]; then
    print_ok "All checks passed"
else
    print_warn "Some checks failed; see above. Fix on VM: sudo systemctl start docker ollama-docker ollama-wrapper-docker"
    exit 1
fi
