#!/bin/bash
# =============================================================================
# Deploy mem-dog (convenience wrapper around manual-deploy.sh)
# =============================================================================
# Runs setup-env, optional setup-postgres/setup-redis/setup-supabase, then deploy-all.
# Pass -p PROJECT_ID and -e ENVIRONMENT. Optionally set USE_POSTGRES_STORAGE, USE_REDIS_STORAGE,
# USE_SUPABASE_STORAGE=true. For Redis: USE_REDIS_STORAGE=true runs deploy-redis
# (GCP Memorystore) if REDIS_URL is not set; otherwise runs setup-redis with your URL.
#
# Usage:
#   ./scripts/deploy.sh -p PROJECT_ID -e dev
#   USE_POSTGRES_STORAGE=true ./scripts/deploy.sh -p PROJECT_ID -e dev
#   USE_REDIS_STORAGE=true ./scripts/deploy.sh -p PROJECT_ID -e dev   # GCP Memorystore
#   USE_REDIS_STORAGE=true REDIS_URL='redis://...' ./scripts/deploy.sh -p PROJECT_ID -e dev  # external Redis
#   USE_SUPABASE_STORAGE=true SUPABASE_URL='...' SUPABASE_SERVICE_ROLE_KEY='...' ./scripts/deploy.sh -p PROJECT_ID -e dev
#   ./scripts/deploy.sh -p PROJECT_ID -e dev --api-only   # deploy API only (no UI, no docs)
#
# Options:
#   -p, --project    GCP Project ID (required)
#   -e, --env        Environment: dev, staging, production (default: dev)
#   -r, --region     GCP Region (default: us-central1)
#   --api-only       Deploy only the API (skip UI and docs)
#   --skip-setup     Skip setup-env (use when env already exists)
#   -h, --help       Show this help
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
PROJECT_ID=""
API_ONLY=""
SKIP_SETUP=""

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
        --api-only)
            API_ONLY=1
            shift
            ;;
        --skip-setup)
            SKIP_SETUP=1
            shift
            ;;
        -h|--help)
            head -35 "$0" | tail -30
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$PROJECT_ID" ]]; then
    echo "ERROR: -p / --project is required" >&2
    exit 1
fi

echo "Deploying mem-dog: project=$PROJECT_ID region=$REGION env=$ENVIRONMENT"
echo ""

if [[ -z "$SKIP_SETUP" ]]; then
    echo "=== setup-env ==="
    "$SCRIPT_DIR/manual-deploy.sh" setup-env -p "$PROJECT_ID" -e "$ENVIRONMENT" -r "$REGION"
fi

if [[ "$USE_POSTGRES_STORAGE" = "true" ]]; then
    echo "=== setup-postgres ==="
    "$SCRIPT_DIR/manual-deploy.sh" setup-postgres -p "$PROJECT_ID" -e "$ENVIRONMENT" -r "$REGION"
fi

if [[ "$USE_REDIS_STORAGE" = "true" ]]; then
    if [[ -n "${REDIS_URL:-}" ]]; then
        echo "=== setup-redis (external Redis) ==="
        REDIS_URL="$REDIS_URL" "$SCRIPT_DIR/manual-deploy.sh" setup-redis -p "$PROJECT_ID" -e "$ENVIRONMENT" -r "$REGION"
    else
        echo "=== deploy-redis (GCP Memorystore) ==="
        "$SCRIPT_DIR/manual-deploy.sh" deploy-redis -p "$PROJECT_ID" -e "$ENVIRONMENT" -r "$REGION"
    fi
fi

if [[ "$USE_SUPABASE_STORAGE" = "true" && -n "${SUPABASE_URL:-}" && -n "${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_KEY:-}}" ]]; then
    echo "=== setup-supabase ==="
    SUPABASE_URL="$SUPABASE_URL" SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-}" SUPABASE_KEY="${SUPABASE_KEY:-}" \
        "$SCRIPT_DIR/manual-deploy.sh" setup-supabase -p "$PROJECT_ID" -e "$ENVIRONMENT" -r "$REGION"
fi

STORAGE_FLAGS="USE_POSTGRES_STORAGE=${USE_POSTGRES_STORAGE:-false} USE_REDIS_STORAGE=${USE_REDIS_STORAGE:-false} USE_SUPABASE_STORAGE=${USE_SUPABASE_STORAGE:-false}"
if [[ -n "$API_ONLY" ]]; then
    echo "=== deploy-api ==="
    $STORAGE_FLAGS "$SCRIPT_DIR/manual-deploy.sh" deploy-api -p "$PROJECT_ID" -e "$ENVIRONMENT" -r "$REGION"
else
    echo "=== deploy-all (API + UI + Docs) ==="
    $STORAGE_FLAGS "$SCRIPT_DIR/manual-deploy.sh" deploy-all -p "$PROJECT_ID" -e "$ENVIRONMENT" -r "$REGION"
fi

echo ""
echo "Deploy complete. Check status: $SCRIPT_DIR/manual-deploy.sh status -p $PROJECT_ID -e $ENVIRONMENT"
