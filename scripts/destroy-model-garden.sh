#!/bin/bash
# =============================================================================
# Destroy model-garden resources only: model servers, download server,
# download Pub/Sub (topic + subscriptions), download Cloud Function, and the
# models GCS bucket. Does not touch API, UI, Postgres, Redis, Chroma, or other
# buckets. Use scripts/destroy.sh to tear down the full environment.
#
# Usage:
#   ./scripts/destroy-model-garden.sh -p PROJECT_ID -e dev --confirm
#   ./scripts/destroy-model-garden.sh -p PROJECT_ID -e dev --confirm --keep-bucket
#
# Options:
#   -p, --project    GCP Project ID (required)
#   -e, --env        Environment: dev, staging, production (default: dev)
#   -r, --region     GCP Region (default: us-central1)
#   --confirm        Required: confirm destruction (no interactive prompt)
#   --keep-bucket    Do not delete the models GCS bucket (preserve model files)
#   -h, --help       Show this help
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
PROJECT_ID=""
CONFIRM=""
KEEP_BUCKET=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error()   { echo -e "${RED}❌ $1${NC}"; }
print_info()    { echo -e "ℹ️  $1"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        --confirm)
            CONFIRM=1
            shift
            ;;
        --keep-bucket)
            KEEP_BUCKET=1
            shift
            ;;
        -h|--help)
            head -25 "$0" | tail -20
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$PROJECT_ID" ]]; then
    print_error "-p / --project is required"
    exit 1
fi

if [[ -z "$CONFIRM" ]]; then
    print_error "Add --confirm to destroy resources (e.g. ./scripts/destroy-model-garden.sh -p $PROJECT_ID -e $ENVIRONMENT --confirm)"
    exit 1
fi

echo ""
echo "========================================="
echo "  Destroy model-garden: $PROJECT_ID / $ENVIRONMENT"
echo "========================================="
echo ""

# 1. Cloud Run: model servers (so nothing new uses the bucket)
SERVICES=(
    "memdog-model-server-small-${ENVIRONMENT}"
    "memdog-model-server-medium-${ENVIRONMENT}"
    "memdog-model-server-large-${ENVIRONMENT}"
    "memdog-model-server-very-large-${ENVIRONMENT}"
)
print_info "Deleting Cloud Run services (model servers)..."
for SVC in "${SERVICES[@]}"; do
    if gcloud run services describe "$SVC" --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        gcloud run services delete "$SVC" --region="$REGION" --project="$PROJECT_ID" --quiet
        print_success "Deleted: $SVC"
    else
        print_warning "Not found (skip): $SVC"
    fi
done

# 2. Pub/Sub: delete subscriptions for the legacy download topic (if any), then the topic
TOPIC="memdog-downloads-${ENVIRONMENT}"
if gcloud pubsub topics describe "$TOPIC" --project="$PROJECT_ID" &>/dev/null; then
    print_info "Deleting Pub/Sub subscriptions for topic $TOPIC..."
    SUBS=$(gcloud pubsub subscriptions list --project="$PROJECT_ID" --filter="topic:projects/$PROJECT_ID/topics/$TOPIC" --format='value(name)' 2>/dev/null || true)
    for SUB in $SUBS; do
        [[ -z "$SUB" ]] && continue
        gcloud pubsub subscriptions delete "$SUB" --project="$PROJECT_ID" --quiet 2>/dev/null && print_success "Deleted subscription: $SUB" || true
    done
    print_info "Deleting Pub/Sub topic: $TOPIC..."
    gcloud pubsub topics delete "$TOPIC" --project="$PROJECT_ID" --quiet
    print_success "Deleted topic: $TOPIC"
else
    print_warning "Not found (skip): $TOPIC"
fi

# 3. Models GCS bucket
if [[ -z "$KEEP_BUCKET" ]]; then
    MODELS_BUCKET="${PROJECT_ID}-memdog-models-${ENVIRONMENT}"
    print_info "Deleting GCS bucket: gs://$MODELS_BUCKET..."
    if gcloud storage buckets describe "gs://$MODELS_BUCKET" --project="$PROJECT_ID" &>/dev/null; then
        gcloud storage rm -r "gs://$MODELS_BUCKET" --project="$PROJECT_ID" 2>/dev/null || true
        print_success "Deleted bucket: $MODELS_BUCKET"
    else
        print_warning "Not found (skip): gs://$MODELS_BUCKET"
    fi
else
    print_info "Skipping models bucket (--keep-bucket)"
fi

echo ""
print_success "Model-garden destroy complete for $ENVIRONMENT in $PROJECT_ID."
echo ""
