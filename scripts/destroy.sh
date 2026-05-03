#!/bin/bash
# =============================================================================
# Destroy mem-dog resources for an environment
# =============================================================================
# Deletes Cloud Run services, Cloud SQL instance, secrets (including Postgres/Redis/Supabase store secrets), and GCS buckets
# created by setup-env / setup-postgres / setup-redis / setup-supabase / deploy-*.
# Requires --confirm to avoid accidental runs.
# To destroy only model-garden (model servers, models bucket), use scripts/destroy-model-garden.sh.
#
# Usage:
#   ./scripts/destroy.sh -p PROJECT_ID -e dev --confirm
#   ./scripts/destroy.sh -p PROJECT_ID -e dev --confirm --keep-buckets   # keep GCS data
#
# Options:
#   -p, --project    GCP Project ID (required)
#   -e, --env        Environment: dev, staging, production (default: dev)
#   -r, --region     GCP Region (default: us-central1)
#   --confirm        Required: confirm destruction (no interactive prompt)
#   --keep-buckets   Do not delete GCS buckets (preserve data)
#   --keep-postgres  Do not delete Cloud SQL instance
#   --keep-redis    Do not delete Memorystore Redis instance
#   -h, --help       Show this help
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
PROJECT_ID=""
CONFIRM=""
KEEP_BUCKETS=""
KEEP_POSTGRES=""
KEEP_REDIS=""

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
        --keep-buckets)
            KEEP_BUCKETS=1
            shift
            ;;
        --keep-postgres)
            KEEP_POSTGRES=1
            shift
            ;;
        --keep-redis)
            KEEP_REDIS=1
            shift
            ;;
        -h|--help)
            head -33 "$0" | tail -28
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
    print_error "Add --confirm to destroy resources (e.g. ./scripts/destroy.sh -p $PROJECT_ID -e $ENVIRONMENT --confirm)"
    exit 1
fi

echo ""
echo "========================================="
echo "  Destroy mem-dog: $PROJECT_ID / $ENVIRONMENT"
echo "========================================="
echo ""

# Cloud Run services (order: dependents first, then API)
SERVICES=(
    "mem-dog-ui-${ENVIRONMENT}"
    "mem-dog-download-server-${ENVIRONMENT}"
    "mem-dog-model-server-small-${ENVIRONMENT}"
    "mem-dog-model-server-medium-${ENVIRONMENT}"
    "mem-dog-model-server-large-${ENVIRONMENT}"
    "mem-dog-model-server-very-large-${ENVIRONMENT}"
    "mem-dog-api"
)

print_info "Deleting Cloud Run services..."
for SVC in "${SERVICES[@]}"; do
    if gcloud run services describe "$SVC" --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        gcloud run services delete "$SVC" --region="$REGION" --project="$PROJECT_ID" --quiet
        print_success "Deleted: $SVC"
    else
        print_warning "Not found (skip): $SVC"
    fi
done

# Cloud SQL instance
if [[ -z "$KEEP_POSTGRES" ]]; then
    INSTANCE_NAME="mem-dog-pg-${ENVIRONMENT}"
    print_info "Deleting Cloud SQL instance: $INSTANCE_NAME..."
    if gcloud sql instances describe "$INSTANCE_NAME" --project="$PROJECT_ID" &>/dev/null; then
        gcloud sql instances delete "$INSTANCE_NAME" --project="$PROJECT_ID" --quiet
        print_success "Deleted: $INSTANCE_NAME"
    else
        print_warning "Not found (skip): $INSTANCE_NAME"
    fi
fi

# Memorystore Redis instance
if [[ -z "$KEEP_REDIS" ]]; then
    REDIS_INSTANCE="mem-dog-redis-${ENVIRONMENT}"
    print_info "Deleting Memorystore Redis instance: $REDIS_INSTANCE..."
    if gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        gcloud redis instances delete "$REDIS_INSTANCE" --region="$REGION" --project="$PROJECT_ID" --quiet
        print_success "Deleted: $REDIS_INSTANCE"
    else
        print_warning "Not found (skip): $REDIS_INSTANCE"
    fi
fi

# Secrets
SECRETS=(
    "mem-dog-postgres-url-${ENVIRONMENT}"
    "mem-dog-redis-url-${ENVIRONMENT}"
    "mem-dog-redis-vpc-${ENVIRONMENT}"
    "mem-dog-supabase-url-${ENVIRONMENT}"
    "mem-dog-supabase-key-${ENVIRONMENT}"
    "mem-dog-api-key-${ENVIRONMENT}"
)
print_info "Deleting secrets..."
for SEC in "${SECRETS[@]}"; do
    if gcloud secrets describe "$SEC" --project="$PROJECT_ID" &>/dev/null; then
        gcloud secrets delete "$SEC" --project="$PROJECT_ID" --quiet
        print_success "Deleted secret: $SEC"
    else
        print_warning "Not found (skip): $SEC"
    fi
done

# GCS buckets
if [[ -z "$KEEP_BUCKETS" ]]; then
    BUCKET_SUFFIXES=(raw meta memories users prompts embeddings viewpoints aiconfig skills stats sysconfig models)
    print_info "Deleting GCS buckets..."
    for suffix in "${BUCKET_SUFFIXES[@]}"; do
        BUCKET="${PROJECT_ID}-mem-dog-${suffix}-${ENVIRONMENT}"
        if gcloud storage buckets describe "gs://$BUCKET" --project="$PROJECT_ID" &>/dev/null; then
            gcloud storage rm -r "gs://$BUCKET" --project="$PROJECT_ID" 2>/dev/null || true
            print_success "Deleted bucket: $BUCKET"
        else
            print_warning "Not found (skip): gs://$BUCKET"
        fi
    done
else
    print_info "Skipping buckets (--keep-buckets)"
fi

# Pub/Sub topic (optional; may be used by download flow)
TOPIC="mem-dog-downloads-${ENVIRONMENT}"
if gcloud pubsub topics describe "$TOPIC" --project="$PROJECT_ID" &>/dev/null; then
    gcloud pubsub topics delete "$TOPIC" --project="$PROJECT_ID" --quiet
    print_success "Deleted topic: $TOPIC"
fi

# Service account (optional; leave if other tools use it)
SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
print_info "Service account $SA_EMAIL left in place (delete manually if desired)."
print_info "Artifact Registry repo 'mem-dog' left in place (delete manually if desired)."

echo ""
print_success "Destroy complete for $ENVIRONMENT in $PROJECT_ID."
echo ""
