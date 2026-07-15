#!/bin/bash
set -e

# =============================================================================
# Manual Deployment Script for mem-dog
# =============================================================================
# This script deploys mem-dog without requiring Workload Identity Federation.
# It uses your local gcloud credentials instead.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - Docker installed and running
#   - You have Owner/Editor access to the GCP project
#
# Usage:
#   ./scripts/manual-deploy.sh [command] [options]
#
# Convenience wrappers:
#   ./scripts/deploy.sh   -p PROJECT -e dev              Run setup-env + deploy-all
#   ./scripts/destroy.sh  -p PROJECT -e dev --confirm    Delete all resources for env
#
# Commands:
#   setup-env           - Create GCP resources (buckets, service accounts, etc.)
#   setup-postgres      - Create Cloud SQL (PostgreSQL 16 + pgvector), store POSTGRES_URL in Secret Manager.
#                         Set USE_POSTGRES_STORAGE=true when running deploy-api to wire it.
#   destroy-postgres    - Delete Cloud SQL instance and Postgres secret for the env. Requires --confirm.
#                         Optional: --keep-instance to keep the instance (delete only the secret).
#   setup-redis         - Store REDIS_URL in Secret Manager (Redis Cloud or external). Set REDIS_URL env var first.
#                         Set USE_REDIS_STORAGE=true when running deploy-api to wire it.
#   deploy-redis        - Provision GCP Memorystore for Redis, store REDIS_URL, wire Cloud Run VPC.
#                         Set USE_REDIS_STORAGE=true when running deploy-api to wire it.
#   setup-supabase      - Store SUPABASE_URL and SUPABASE_KEY in Secret Manager. Set env vars first.
#                         Set USE_SUPABASE_STORAGE=true when running deploy-api to wire it.
#   deploy-api          - Build and deploy the API. Auto-wires WEBHOOK_GATEWAY_URL and
#                         WEBHOOK_API_KEY when webhook is deployed. Override: MEM_DOG_WEBHOOK_GATEWAY_URL,
#                         MEM_DOG_WEBHOOK_API_KEY.
#   deploy-ui           - Build and deploy the UI. Auto-wires Testing tab and OpenClaw Chat tab.
#                         Override: MEM_DOG_WEBHOOK_GATEWAY_URL, MEM_DOG_WEBHOOK_API_KEY,
#                         NEXT_PUBLIC_WEBHOOK_GATEWAY_URL, NEXT_PUBLIC_WEBHOOK_API_KEY (or WGW_API_KEY).
#   deploy-ui-read      - Build and deploy read-only UI (no login, no write operations).
#                         Deployed as separate Cloud Run service: mem-dog-ui-read-<env>.
#   deploy-api-docs     - Build and deploy the API (same as deploy-api)
#   deploy-all          - Deploy API and UI
#   deploy-model-servers [tier ...] - Deploy AI Chat model servers (default: all 4 tiers).
#                          Optional: pass one or more of small, medium, large, very-large
#                          to deploy only those tiers. Creates models bucket, grants IAM,
#                          deploys Cloud Run services. Model servers are NOT auto-wired to
#                          the API; add them manually via UI or MODEL_SERVER_URL_* env vars.
#                          Tier CPU/memory are read from scripts/gcp-cloudrun-options.json when
#                          present (requires jq). Use --list-cloudrun to show tier config and exit.
#   deploy-vm-instance [type] - Provision GCP VM instance with GPU.
#                          Use scripts/gcp-vm-options.json for VM types and models (requires jq).
#                          Optional: --list-vms (list VM types), --vm TYPE, --model NAME.
#                          TYPE: instance index (1-4), instance_type label, or legacy machine type.
#                          MODEL: display name (e.g. "Gemma-3-12B") or catalog_model_id (e.g. gemma-3-12b).
#                          Default: a2-highgpu-1g. See docs/guides/VM_MODEL_CATALOG_ALIGNMENT.md for catalog mapping.
#   setup-webhook       - Create webhook infrastructure (APIs, Pub/Sub, SA, IAM)
#   deploy-model-server - Deploy Ollama model server to Cloud Run (webhook pipeline)
#   deploy-agent        - Deploy ADK agent to Cloud Run (Cloud Run A)
#   deploy-webhook      - Deploy webhook Cloud Functions and API Gateway
#   deploy-webhook-gateway - Build and deploy the Webhook Gateway to Cloud Run.
#                          Supports 25+ inbound channels and 20+ LLM providers.
#                          Auto-wires WEBHOOK_GATEWAY_URL and MEM_DOG_API_URL.
#                          LLM provider: LLM_PROVIDER (default: gemini). API keys via
#                          Secret Manager or env vars (GEMINI_API_KEY, LLM_API_KEY, etc.).
#   deploy-webhook-gateway-gke - Build and deploy the Webhook Gateway to GKE.
#                          Uses k8s/webhook-gateway/ manifests and the "open-jaws" Gateway.
#                          Set GKE_CLUSTER and GKE_ZONE to target your cluster.
#   deploy-openclaw-node-gke - Build and deploy the OpenClaw Node.js service to GKE.
#                          Runs alongside the Python gateway, routes /oc/* to it.
#                          Bridges messages to the Python gateway via /webhooks/openclaw.
#   deploy-supabase-gke - Deploy self-hosted Supabase stack to GKE (Postgres+pgvector,
#                          PostgREST, GoTrue, Kong, Realtime, Meta, Studio). Seeds mem-dog
#                          tables. Stores credentials in Secret Manager. Creates
#                          api-supabase-secrets in mem-dog namespace for API wiring.
#   redeploy-supabase-gke - Re-apply Supabase manifests and re-run seed in GKE, reusing
#                          existing supabase-secrets so credentials and data are preserved.
#                          Set GKE_CLUSTER and GKE_ZONE to target your cluster.
#   seed-supabase-gke   - Re-run the Supabase seed job (schema updates). Idempotent.
#   destroy-supabase-data-gke - Wipe mem-dog data from Supabase tables (keeps environment).
#                          Requires --confirm.
#   destroy-supabase-gke - Delete entire Supabase namespace and all resources.
#                          Requires --confirm. Optional: --delete-secrets to also remove
#                          Secret Manager entries.
#   status              - Show deployment status (includes URL dependencies and API env vars)
#   restart-gke         - Rollout restart all deployments (and statefulsets) in mem-dog, webhook-gateway,
#                         webhook-pipeline, and supabase namespaces. Use after config/secret changes.
#
# When running any deploy command, a URL-dependencies check runs first and prints
# resolved URLs (API, UI, model tiers) and current API env vars.
#
# Options:
#   -p, --project    GCP Project ID (required)
#   -r, --region     GCP Region (default: us-central1)
#   -e, --env        Environment: dev, staging, production (default: dev)
#   --confirm        Required for destroy-postgres (avoids accidental teardown)
#   --keep-instance  For destroy-postgres only: do not delete Cloud SQL instance (delete only the secret)
#   -h, --help       Show this help message
# =============================================================================

# Default values
REGION="us-central1"
ENVIRONMENT="dev"
PROJECT_ID=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Load shared AI model defaults (GEMINI_MODEL, GEMINI_LITELLM_MODEL, etc.)
# shellcheck source=../config/ai.env
source "$ROOT_DIR/config/ai.env" 2>/dev/null || true

# =============================================================================
# Store backends (deploy-api wiring)
# =============================================================================
# Postgres / Redis / Supabase: set to "true" to wire the API when running deploy-api.
# Requires running the corresponding setup-* command first (setup-postgres, setup-redis, setup-supabase).
#
# Usage:
#   USE_POSTGRES_STORAGE=true ./scripts/manual-deploy.sh deploy-api -p PROJECT -e dev
#   USE_REDIS_STORAGE=true   ./scripts/manual-deploy.sh deploy-api -p PROJECT -e dev
#   USE_SUPABASE_STORAGE=true ./scripts/manual-deploy.sh deploy-api -p PROJECT -e dev
#     (override GKE_VPC_NETWORK when Kong runs in a non-default VPC; default: "default")
#
USE_POSTGRES_STORAGE="${USE_POSTGRES_STORAGE:-false}"
USE_REDIS_STORAGE="${USE_REDIS_STORAGE:-false}"
USE_SUPABASE_STORAGE="${USE_SUPABASE_STORAGE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Print remediation steps when something fails
print_howto() {
    echo ""
    echo -e "${YELLOW}To fix / How to succeed:${NC}"
    while [[ $# -gt 0 ]]; do
        echo -e "  ${YELLOW}•${NC} $1"
        shift
    done
    echo ""
}

show_help() {
    head -40 "$0" | tail -35
    exit 0
}

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed"
        exit 1
    fi
    print_success "gcloud CLI found"

    # destroy-postgres only needs gcloud (no Docker/uv)
    if [ "$COMMAND" = "destroy-postgres" ]; then
        if ! gcloud auth print-access-token &> /dev/null; then
            print_error "Not authenticated with gcloud. Run: gcloud auth login"
            exit 1
        fi
        print_success "gcloud authenticated"
        if [ -z "$PROJECT_ID" ]; then
            print_error "Project ID is required. Use -p or --project"
            exit 1
        fi
        if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
            print_error "Project $PROJECT_ID does not exist or you don't have access"
            exit 1
        fi
        print_success "Project exists and accessible"
        return 0
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_success "Docker found"
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        exit 1
    fi
    print_success "Docker daemon is running"

    # Check uv
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    print_success "uv found ($(uv --version))"
    
    # Check gcloud auth
    if ! gcloud auth print-access-token &> /dev/null; then
        print_error "Not authenticated with gcloud. Run: gcloud auth login"
        exit 1
    fi
    print_success "gcloud authenticated"
    
    # Verify project ID
    if [ -z "$PROJECT_ID" ]; then
        print_error "Project ID is required. Use -p or --project"
        exit 1
    fi
    print_success "Project ID: $PROJECT_ID"
    
    # Verify project exists
    if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        print_error "Project $PROJECT_ID does not exist or you don't have access"
        exit 1
    fi
    print_success "Project exists and accessible"
}

# =============================================================================
# Setup PostgreSQL (Cloud SQL + pgvector)
# =============================================================================

setup_postgres() {
    print_header "Setting Up Cloud SQL (PostgreSQL 16 + pgvector): $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        echo "ERROR: --project is required" >&2
        exit 1
    fi

    local INSTANCE_NAME="mem-dog-pg-${ENVIRONMENT}"
    local DB_NAME="memdog"
    local DB_USER="memdog"
    local SECRET_NAME="mem-dog-postgres-url-${ENVIRONMENT}"
    local SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"

    # ── Enable required APIs ────────────────────────────────────────────────
    print_info "Enabling Cloud SQL, Secret Manager, and Compute APIs..."
    gcloud services enable \
        sqladmin.googleapis.com \
        secretmanager.googleapis.com \
        compute.googleapis.com \
        servicenetworking.googleapis.com \
        --project="$PROJECT_ID" --quiet
    print_success "APIs enabled"

    # ── Create Cloud SQL instance ────────────────────────────────────────────
    if gcloud sql instances describe "$INSTANCE_NAME" \
            --project="$PROJECT_ID" &>/dev/null; then
        print_warning "Cloud SQL instance $INSTANCE_NAME already exists — skipping creation"
    else
        # ── Private IP: enable Service Networking and VPC peering ──────────────
        print_info "Enabling Service Networking API (required for private IP)..."
        gcloud services enable servicenetworking.googleapis.com \
            --project="$PROJECT_ID" --quiet

        # Allocate an IP range for Google-managed services (idempotent)
        if ! gcloud compute addresses describe google-managed-services-default \
                --global --project="$PROJECT_ID" &>/dev/null; then
            print_info "Allocating IP range for VPC peering..."
            gcloud compute addresses create google-managed-services-default \
                --project="$PROJECT_ID" \
                --global \
                --purpose=VPC_PEERING \
                --prefix-length=16 \
                --network=default \
                --quiet
            print_success "IP range allocated"
        else
            print_warning "IP range google-managed-services-default already exists — skipping"
        fi

        # Create VPC peering (idempotent — update if already exists)
        print_info "Creating VPC peering for Service Networking..."
        gcloud services vpc-peerings connect \
            --project="$PROJECT_ID" \
            --service=servicenetworking.googleapis.com \
            --ranges=google-managed-services-default \
            --network=default \
            --quiet || true
        print_success "VPC peering ready"

        print_info "Creating Cloud SQL instance $INSTANCE_NAME (PostgreSQL 16, private IP)..."
        gcloud sql instances create "$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --database-version=POSTGRES_16 \
            --region="$REGION" \
            --edition=ENTERPRISE \
            --tier=db-custom-1-3840 \
            --storage-auto-increase \
            --no-assign-ip \
            --network=default \
            --quiet
        print_success "Cloud SQL instance created: $INSTANCE_NAME"
    fi

    # ── Create database ──────────────────────────────────────────────────────
    if gcloud sql databases describe "$DB_NAME" \
            --instance="$INSTANCE_NAME" --project="$PROJECT_ID" &>/dev/null; then
        print_warning "Database $DB_NAME already exists — skipping"
    else
        print_info "Creating database $DB_NAME..."
        gcloud sql databases create "$DB_NAME" \
            --instance="$INSTANCE_NAME" \
            --project="$PROJECT_ID" --quiet
        print_success "Database created: $DB_NAME"
    fi

    # ── Enable pgvector extension ────────────────────────────────────────────
    # pgvector is bundled with Cloud SQL PostgreSQL 14+; no instance flag needed.
    # We enable it in the database after creation via the Cloud SQL built-in
    # superuser connection (gcloud sql connect --user=postgres).
    print_info "Enabling pgvector extension in $DB_NAME (via postgres superuser)..."
    echo "CREATE EXTENSION IF NOT EXISTS vector;" | \
        gcloud sql connect "$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --database="$DB_NAME" \
            --user=postgres --quiet 2>/dev/null || \
        print_warning "Could not auto-enable pgvector — run manually: CREATE EXTENSION IF NOT EXISTS vector;"
    print_success "pgvector extension ready"

    # ── Create / reset DB user ───────────────────────────────────────────────
    local DB_PASSWORD
    DB_PASSWORD="$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)"
    print_info "Setting password for DB user $DB_USER..."
    if gcloud sql users list --instance="$INSTANCE_NAME" \
            --project="$PROJECT_ID" --format="value(name)" 2>/dev/null \
            | grep -q "^${DB_USER}$"; then
        gcloud sql users set-password "$DB_USER" \
            --instance="$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --password="$DB_PASSWORD" --quiet
        print_success "DB user password updated"
    else
        gcloud sql users create "$DB_USER" \
            --instance="$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --password="$DB_PASSWORD" --quiet
        print_success "DB user created: $DB_USER"
    fi

    # ── Build connection string ──────────────────────────────────────────────
    # Cloud Run uses the Cloud SQL Auth Proxy via Unix socket
    local CONNECTION_NAME
    CONNECTION_NAME="${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"
    local POSTGRES_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"

    # ── Store in Secret Manager ──────────────────────────────────────────────
    print_info "Storing POSTGRES_URL in Secret Manager as $SECRET_NAME..."
    if gcloud secrets describe "$SECRET_NAME" \
            --project="$PROJECT_ID" &>/dev/null; then
        echo -n "$POSTGRES_URL" | gcloud secrets versions add "$SECRET_NAME" \
            --data-file=- --project="$PROJECT_ID" --quiet
        print_success "Secret updated: $SECRET_NAME"
    else
        echo -n "$POSTGRES_URL" | gcloud secrets create "$SECRET_NAME" \
            --data-file=- --project="$PROJECT_ID" --replication-policy=automatic --quiet
        print_success "Secret created: $SECRET_NAME"
    fi

    # ── Grant schema privileges to DB user ──────────────────────────────────
    # PostgreSQL 15+ removed CREATE from the public schema default privileges.
    # Without this, create_all() fails silently and postgres_store stays None.
    print_info "Granting public schema privileges to $DB_USER..."
    {
        echo "GRANT CREATE ON SCHEMA public TO ${DB_USER};"
        echo "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};"
        echo "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};"
        echo "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};"
        echo "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};"
    } | PGPASSWORD="$DB_PASSWORD" gcloud sql connect "$INSTANCE_NAME" \
        --project="$PROJECT_ID" \
        --database="$DB_NAME" \
        --user=postgres --quiet 2>/dev/null || \
        print_warning "Could not auto-grant schema privileges — run scripts/fix-postgres-permissions.sh if vm-instances/public-llms fail"
    print_success "Schema privileges granted to $DB_USER"

    # ── Grant API service account access ────────────────────────────────────
    print_info "Granting roles/cloudsql.client to $SA_EMAIL..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/cloudsql.client" --quiet 2>/dev/null || true
    print_success "roles/cloudsql.client granted"

    print_info "Granting Secret Manager accessor to $SA_EMAIL..."
    gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" --quiet
    print_success "Secret accessor granted"

    # ── Summary ─────────────────────────────────────────────────────────────
    echo ""
    print_success "Cloud SQL setup complete!"
    echo ""
    echo "  Instance    : $INSTANCE_NAME"
    echo "  Connection  : $CONNECTION_NAME"
    echo "  Secret      : $SECRET_NAME"
    echo ""
    echo "Next step: set USE_POSTGRES_STORAGE=true and run deploy-api to wire POSTGRES_URL."
}

# =============================================================================
# Destroy PostgreSQL (Cloud SQL instance and secret)
# =============================================================================
# Requires --confirm. Use --keep-instance to keep the Cloud SQL instance (delete only the secret).
# =============================================================================

destroy_postgres() {
    print_header "Destroying PostgreSQL: $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        print_error "--project is required"
        exit 1
    fi

    if [ -z "${CONFIRM:-}" ]; then
        print_error "Add --confirm to destroy Postgres (e.g. ./scripts/manual-deploy.sh destroy-postgres -p $PROJECT_ID -e $ENVIRONMENT --confirm)"
        exit 1
    fi

    local INSTANCE_NAME="mem-dog-pg-${ENVIRONMENT}"
    local SECRET_NAME="mem-dog-postgres-url-${ENVIRONMENT}"

    # Cloud SQL instance (unless --keep-instance)
    if [ -z "${KEEP_INSTANCE:-}" ]; then
        print_info "Deleting Cloud SQL instance: $INSTANCE_NAME..."
        if gcloud sql instances describe "$INSTANCE_NAME" --project="$PROJECT_ID" &>/dev/null; then
            gcloud sql instances delete "$INSTANCE_NAME" --project="$PROJECT_ID" --quiet
            print_success "Deleted: $INSTANCE_NAME"
        else
            print_warning "Not found (skip): $INSTANCE_NAME"
        fi
    else
        print_info "Skipping Cloud SQL instance (--keep-instance)"
    fi

    # Secret
    if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        gcloud secrets delete "$SECRET_NAME" --project="$PROJECT_ID" --quiet
        print_success "Deleted secret: $SECRET_NAME"
    else
        print_warning "Not found (skip): $SECRET_NAME"
    fi

    echo ""
    print_success "PostgreSQL destroy complete for $ENVIRONMENT in $PROJECT_ID."
    echo ""
}

# =============================================================================
# Setup Redis (Secret Manager only; Redis Cloud or self-hosted URL)
# =============================================================================

setup_redis() {
    print_header "Setting Up Redis storage secret: $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        echo "ERROR: --project is required" >&2
        exit 1
    fi

    if [ -z "${REDIS_URL:-}" ]; then
        print_error "REDIS_URL is required. Set it to your Redis connection string (e.g. redis://localhost:6379/0 or Redis Cloud URL)."
        echo ""
        echo "  REDIS_URL='rediss://default:PASSWORD@HOST:6379' $0 setup-redis -p $PROJECT_ID -e $ENVIRONMENT"
        exit 1
    fi

    local SECRET_NAME="mem-dog-redis-url-${ENVIRONMENT}"
    local SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"

    print_info "Storing REDIS_URL in Secret Manager as $SECRET_NAME..."
    if gcloud secrets describe "$SECRET_NAME" \
            --project="$PROJECT_ID" &>/dev/null; then
        echo -n "$REDIS_URL" | gcloud secrets versions add "$SECRET_NAME" \
            --data-file=- --project="$PROJECT_ID" --quiet
        print_success "Secret updated: $SECRET_NAME"
    else
        echo -n "$REDIS_URL" | gcloud secrets create "$SECRET_NAME" \
            --data-file=- --project="$PROJECT_ID" --replication-policy=automatic --quiet
        print_success "Secret created: $SECRET_NAME"
    fi

    print_info "Granting Secret Manager accessor to $SA_EMAIL..."
    gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" --quiet
    print_success "Secret accessor granted"

    echo ""
    print_success "Redis storage secret ready!"
    echo ""
    echo "  Secret: $SECRET_NAME"
    echo ""
    echo "Next step: set USE_REDIS_STORAGE=true and run deploy-api to wire REDIS_URL."
}

# =============================================================================
# Deploy Redis (GCP Memorystore) — provision instance, store REDIS_URL, mark for VPC
# =============================================================================

deploy_redis() {
    print_header "Deploying GCP Memorystore for Redis: $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        echo "ERROR: --project is required" >&2
        exit 1
    fi

    local SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        print_error "Service account $SA_EMAIL not found. Run setup-env first."
        exit 1
    fi

    local INSTANCE_NAME="mem-dog-redis-${ENVIRONMENT}"
    local SECRET_NAME="mem-dog-redis-url-${ENVIRONMENT}"
    local VPC_SECRET_NAME="mem-dog-redis-vpc-${ENVIRONMENT}"

    # ── Enable APIs ─────────────────────────────────────────────────────────
    print_info "Enabling Redis and Secret Manager APIs..."
    gcloud services enable redis.googleapis.com secretmanager.googleapis.com \
        compute.googleapis.com servicenetworking.googleapis.com \
        --project="$PROJECT_ID" --quiet
    print_success "APIs enabled"

    # ── Ensure VPC peering for Private Service Access (same as setup-postgres) ─
    if ! gcloud compute addresses describe google-managed-services-default \
            --global --project="$PROJECT_ID" &>/dev/null; then
        print_info "Allocating IP range for VPC peering..."
        gcloud compute addresses create google-managed-services-default \
            --project="$PROJECT_ID" \
            --global \
            --purpose=VPC_PEERING \
            --prefix-length=16 \
            --network=default \
            --quiet
        print_success "IP range allocated"
    fi

    gcloud services vpc-peerings connect \
        --project="$PROJECT_ID" \
        --service=servicenetworking.googleapis.com \
        --ranges=google-managed-services-default \
        --network=default \
        --quiet 2>/dev/null || true
    print_success "VPC peering ready"

    # ── Create Memorystore instance ─────────────────────────────────────────
    if gcloud redis instances describe "$INSTANCE_NAME" \
            --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        print_warning "Memorystore instance $INSTANCE_NAME already exists — skipping creation"
    else
        print_info "Creating Memorystore instance $INSTANCE_NAME (1 GB Basic, ~5 min)..."
        gcloud redis instances create "$INSTANCE_NAME" \
            --project="$PROJECT_ID" \
            --region="$REGION" \
            --size=1 \
            --redis-version=redis_7_0 \
            --network=default \
            --connect-mode=PRIVATE_SERVICE_ACCESS \
            --quiet
        print_success "Memorystore instance created: $INSTANCE_NAME"
    fi

    # ── Get host IP ─────────────────────────────────────────────────────────
    local REDIS_HOST
    REDIS_HOST=$(gcloud redis instances describe "$INSTANCE_NAME" \
        --region="$REGION" --project="$PROJECT_ID" \
        --format='value(host)' 2>/dev/null)
    if [ -z "$REDIS_HOST" ]; then
        print_error "Could not get Redis instance host IP"
        exit 1
    fi
    local REDIS_URL="redis://${REDIS_HOST}:6379/0"
    print_success "Redis host: $REDIS_HOST"

    # ── Store REDIS_URL in Secret Manager ────────────────────────────────────
    print_info "Storing REDIS_URL in Secret Manager as $SECRET_NAME..."
    if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        echo -n "$REDIS_URL" | gcloud secrets versions add "$SECRET_NAME" \
            --data-file=- --project="$PROJECT_ID" --quiet
        print_success "Secret updated: $SECRET_NAME"
    else
        echo -n "$REDIS_URL" | gcloud secrets create "$SECRET_NAME" \
            --data-file=- --project="$PROJECT_ID" --replication-policy=automatic --quiet
        print_success "Secret created: $SECRET_NAME"
    fi

    # ── Mark that Redis uses VPC (Cloud Run needs Direct VPC egress) ─────────
    print_info "Marking Redis as VPC-backed for deploy-api..."
    if gcloud secrets describe "$VPC_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        echo -n "1" | gcloud secrets versions add "$VPC_SECRET_NAME" \
            --data-file=- --project="$PROJECT_ID" --quiet
    else
        echo -n "1" | gcloud secrets create "$VPC_SECRET_NAME" \
            --data-file=- --project="$PROJECT_ID" --replication-policy=automatic --quiet
    fi
    print_success "VPC marker set: $VPC_SECRET_NAME"

    # ── Grant API service account access ─────────────────────────────────────
    print_info "Granting Secret Manager accessor to $SA_EMAIL..."
    for s in "$SECRET_NAME" "$VPC_SECRET_NAME"; do
        gcloud secrets add-iam-policy-binding "$s" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" \
            --project="$PROJECT_ID" --quiet
    done
    print_success "Secret accessor granted"

    echo ""
    print_success "GCP Memorystore Redis ready!"
    echo ""
    echo "  Instance: $INSTANCE_NAME"
    echo "  Secret:   $SECRET_NAME"
    echo ""
    echo "Next step: USE_REDIS_STORAGE=true ./scripts/manual-deploy.sh deploy-api -p $PROJECT_ID -e $ENVIRONMENT"
}

setup_supabase() {
    print_header "Setting up Supabase store secrets: $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        echo "ERROR: --project is required" >&2
        exit 1
    fi

    if [ -z "${SUPABASE_URL:-}" ]; then
        print_error "SUPABASE_URL is required (e.g. https://xxxx.supabase.co)."
        exit 1
    fi
    local KEY_VAL="${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_KEY:-}}"
    if [ -z "$KEY_VAL" ]; then
        print_error "Set SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY."
        echo ""
        echo "  SUPABASE_URL='https://xxxx.supabase.co' SUPABASE_SERVICE_ROLE_KEY='...' $0 setup-supabase -p $PROJECT_ID -e $ENVIRONMENT"
        exit 1
    fi

    local URL_SECRET="mem-dog-supabase-url-${ENVIRONMENT}"
    local KEY_SECRET="mem-dog-supabase-key-${ENVIRONMENT}"
    local SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"

    print_info "Storing SUPABASE_URL in Secret Manager as $URL_SECRET..."
    if gcloud secrets describe "$URL_SECRET" --project="$PROJECT_ID" &>/dev/null; then
        echo -n "$SUPABASE_URL" | gcloud secrets versions add "$URL_SECRET" \
            --data-file=- --project="$PROJECT_ID" --quiet
        print_success "Secret updated: $URL_SECRET"
    else
        echo -n "$SUPABASE_URL" | gcloud secrets create "$URL_SECRET" \
            --data-file=- --project="$PROJECT_ID" --replication-policy=automatic --quiet
        print_success "Secret created: $URL_SECRET"
    fi
    gcloud secrets add-iam-policy-binding "$URL_SECRET" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" --quiet

    print_info "Storing Supabase key in Secret Manager as $KEY_SECRET..."
    if gcloud secrets describe "$KEY_SECRET" --project="$PROJECT_ID" &>/dev/null; then
        echo -n "$KEY_VAL" | gcloud secrets versions add "$KEY_SECRET" \
            --data-file=- --project="$PROJECT_ID" --quiet
        print_success "Secret updated: $KEY_SECRET"
    else
        echo -n "$KEY_VAL" | gcloud secrets create "$KEY_SECRET" \
            --data-file=- --project="$PROJECT_ID" --replication-policy=automatic --quiet
        print_success "Secret created: $KEY_SECRET"
    fi
    gcloud secrets add-iam-policy-binding "$KEY_SECRET" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" --quiet

    echo ""
    print_success "Supabase store secrets ready!"
    echo ""
    echo "Next step: set USE_SUPABASE_STORAGE=true and run deploy-api to wire Supabase."
}

# =============================================================================
# Deploy Supabase to GKE (self-hosted full stack)
# =============================================================================
# Redeploy Supabase on GKE (reuse existing secrets)
# =============================================================================

redeploy_supabase_gke() {
    if [ -z "$PROJECT_ID" ]; then
        print_error "--project is required"
        exit 1
    fi

    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    if kubectl get secret supabase-secrets -n supabase &>/dev/null; then
        print_info "Loading existing supabase-secrets from cluster (credentials preserved)..."
        export SUPABASE_PG_PASSWORD=$(kubectl get secret supabase-secrets -n supabase -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d 2>/dev/null || true)
        export SUPABASE_JWT_SECRET=$(kubectl get secret supabase-secrets -n supabase -o jsonpath='{.data.JWT_SECRET}' | base64 -d 2>/dev/null || true)
        export SUPABASE_ANON_KEY=$(kubectl get secret supabase-secrets -n supabase -o jsonpath='{.data.ANON_KEY}' | base64 -d 2>/dev/null || true)
        export SUPABASE_SERVICE_ROLE_KEY=$(kubectl get secret supabase-secrets -n supabase -o jsonpath='{.data.SERVICE_ROLE_KEY}' | base64 -d 2>/dev/null || true)
        if [ -n "$SUPABASE_JWT_SECRET" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
            print_success "Using existing credentials"
        else
            print_warning "Could not read all keys from supabase-secrets — deploy may regenerate some"
        fi
    else
        print_warning "supabase-secrets not found in supabase namespace. Run deploy-supabase-gke first for a fresh deploy."
    fi

    deploy_supabase_gke
}

# =============================================================================
# Deploy Supabase to GKE
# =============================================================================

deploy_supabase_gke() {
    print_header "Deploying self-hosted Supabase to GKE: $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        print_error "--project is required"
        exit 1
    fi

    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"
    K8S_DIR="$ROOT_DIR/k8s/supabase"

    # ── Connect to GKE cluster ──────────────────────────────────────────────
    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            echo ""
            echo "Set GKE_CLUSTER and GKE_ZONE:"
            echo "  GKE_CLUSTER=my-cluster GKE_ZONE=${REGION}-a $0 deploy-supabase-gke -p $PROJECT_ID -e $ENVIRONMENT"
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    if ! command -v kubectl &>/dev/null; then
        print_error "kubectl not found. Install: gcloud components install kubectl"
        exit 1
    fi

    # ── Generate or resolve secrets ─────────────────────────────────────────
    local JWT_SECRET ANON_KEY SERVICE_ROLE_KEY PG_PASSWORD
    local URL_SECRET_NAME="mem-dog-supabase-url-${ENVIRONMENT}"
    local KEY_SECRET_NAME="mem-dog-supabase-key-${ENVIRONMENT}"
    local JWT_SECRET_NAME="mem-dog-supabase-jwt-secret-${ENVIRONMENT}"
    local PG_SECRET_NAME="mem-dog-supabase-pg-password-${ENVIRONMENT}"

    # Prefer env vars; then try Secret Manager (so destroy+deploy reuses existing secrets)
    if [ -z "${SUPABASE_PG_PASSWORD:-}" ] && gcloud secrets describe "$PG_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        SUPABASE_PG_PASSWORD=$(gcloud secrets versions access latest --secret="$PG_SECRET_NAME" --project="$PROJECT_ID" 2>/dev/null || true)
        if [ -n "$SUPABASE_PG_PASSWORD" ]; then
            print_info "Using POSTGRES_PASSWORD from Secret Manager ($PG_SECRET_NAME)"
        fi
    fi
    if [ -z "${SUPABASE_JWT_SECRET:-}" ] && gcloud secrets describe "$JWT_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        SUPABASE_JWT_SECRET=$(gcloud secrets versions access latest --secret="$JWT_SECRET_NAME" --project="$PROJECT_ID" 2>/dev/null || true)
        if [ -n "$SUPABASE_JWT_SECRET" ]; then
            print_info "Using JWT_SECRET from Secret Manager ($JWT_SECRET_NAME)"
        fi
    fi
    if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ] && gcloud secrets describe "$KEY_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        SUPABASE_SERVICE_ROLE_KEY=$(gcloud secrets versions access latest --secret="$KEY_SECRET_NAME" --project="$PROJECT_ID" 2>/dev/null || true)
        if [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
            print_info "Using SERVICE_ROLE_KEY from Secret Manager ($KEY_SECRET_NAME)"
        fi
    fi

    PG_PASSWORD="${SUPABASE_PG_PASSWORD:-$(openssl rand -base64 32 | tr -d '\n/+=')}"

    if [ -n "${SUPABASE_JWT_SECRET:-}" ]; then
        JWT_SECRET="$SUPABASE_JWT_SECRET"
    else
        JWT_SECRET=$(openssl rand -base64 64 | tr -d '\n')
        print_info "Generated JWT_SECRET (set SUPABASE_JWT_SECRET to override)"
    fi

    if [ -n "${SUPABASE_ANON_KEY:-}" ]; then
        ANON_KEY="$SUPABASE_ANON_KEY"
    else
        if command -v python3 &>/dev/null; then
            ANON_KEY=$(python3 -c "
import jwt
print(jwt.encode({'role': 'anon', 'iss': 'supabase', 'iat': 1700000000, 'exp': 2000000000}, '''$JWT_SECRET''', algorithm='HS256'))
" 2>/dev/null || echo "")
        fi
        if [ -z "$ANON_KEY" ]; then
            print_error "Could not generate ANON_KEY. Set SUPABASE_ANON_KEY or install pyjwt (pip install pyjwt)."
            exit 1
        fi
        print_info "Generated ANON_KEY from JWT_SECRET"
    fi

    if [ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
        SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY"
    else
        if command -v python3 &>/dev/null; then
            SERVICE_ROLE_KEY=$(python3 -c "
import jwt
print(jwt.encode({'role': 'service_role', 'iss': 'supabase', 'iat': 1700000000, 'exp': 2000000000}, '''$JWT_SECRET''', algorithm='HS256'))
" 2>/dev/null || echo "")
        fi
        if [ -z "$SERVICE_ROLE_KEY" ]; then
            print_error "Could not generate SERVICE_ROLE_KEY. Set SUPABASE_SERVICE_ROLE_KEY or install pyjwt."
            exit 1
        fi
        print_info "Generated SERVICE_ROLE_KEY from JWT_SECRET"
    fi

    # ── Apply K8s manifests in dependency order ─────────────────────────────
    print_info "Applying Supabase K8s manifests..."

    kubectl apply -f "$K8S_DIR/namespace.yaml"

    # Create/update secrets
    kubectl -n supabase create secret generic supabase-secrets \
        --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD" \
        --from-literal=JWT_SECRET="$JWT_SECRET" \
        --from-literal=ANON_KEY="$ANON_KEY" \
        --from-literal=SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
        --from-literal=DASHBOARD_USERNAME="${SUPABASE_DASHBOARD_USERNAME:-supabase}" \
        --from-literal=DASHBOARD_PASSWORD="${SUPABASE_DASHBOARD_PASSWORD:-$PG_PASSWORD}" \
        --dry-run=client -o yaml | kubectl apply -f -
    print_success "Secrets applied"

    # Postgres (DB init ConfigMap, PVC, StatefulSet, Service)
    kubectl apply -f "$K8S_DIR/postgres-configmap.yaml"
    kubectl apply -f "$K8S_DIR/postgres-pvc.yaml"
    kubectl apply -f "$K8S_DIR/postgres-statefulset.yaml"
    kubectl apply -f "$K8S_DIR/postgres-service.yaml"

    print_info "Waiting for Postgres to be ready..."
    kubectl rollout status statefulset/supabase-db -n supabase --timeout=180s
    print_success "Postgres ready"

    # PostgREST
    kubectl apply -f "$K8S_DIR/postgrest-deployment.yaml"
    kubectl apply -f "$K8S_DIR/postgrest-service.yaml"

    # GoTrue (Auth)
    kubectl apply -f "$K8S_DIR/gotrue-deployment.yaml"
    kubectl apply -f "$K8S_DIR/gotrue-service.yaml"

    # Realtime
    kubectl apply -f "$K8S_DIR/realtime-deployment.yaml"
    kubectl apply -f "$K8S_DIR/realtime-service.yaml"

    # Meta (Postgres Meta)
    kubectl apply -f "$K8S_DIR/meta-deployment.yaml"
    kubectl apply -f "$K8S_DIR/meta-service.yaml"

    # Kong (API Gateway)
    kubectl apply -f "$K8S_DIR/kong-configmap.yaml"
    kubectl apply -f "$K8S_DIR/kong-deployment.yaml"
    kubectl apply -f "$K8S_DIR/kong-service.yaml"

    # Studio
    kubectl apply -f "$K8S_DIR/studio-deployment.yaml"
    kubectl apply -f "$K8S_DIR/studio-service.yaml"

    # ── Run seed job ────────────────────────────────────────────────────────
    print_info "Seeding mem-dog tables..."
    kubectl apply -f "$K8S_DIR/seed-configmap.yaml"
    kubectl delete job supabase-seed -n supabase --ignore-not-found
    kubectl apply -f "$K8S_DIR/seed-job.yaml"
    kubectl wait --for=condition=complete job/supabase-seed -n supabase --timeout=120s
    print_success "Seed complete"

    # ── Wait for all deployments ────────────────────────────────────────────
    print_info "Waiting for all Supabase deployments to roll out..."
    for dep in supabase-rest supabase-auth supabase-realtime supabase-meta supabase-kong supabase-studio; do
        kubectl rollout status deployment/$dep -n supabase --timeout=120s 2>/dev/null || \
            print_warning "Deployment $dep not ready yet (non-fatal)"
    done
    print_success "Supabase stack deployed"

    # ── Store Supabase URL and keys in Secret Manager ────────────────────────
    local SUPABASE_URL="http://supabase-kong.supabase.svc.cluster.local:8000"
    local SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"

    _upsert_secret() {
        local name="$1" value="$2"
        if gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null; then
            echo -n "$value" | gcloud secrets versions add "$name" \
                --data-file=- --project="$PROJECT_ID" --quiet
        else
            echo -n "$value" | gcloud secrets create "$name" \
                --data-file=- --project="$PROJECT_ID" --replication-policy=automatic --quiet
        fi
        gcloud secrets add-iam-policy-binding "$name" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" \
            --project="$PROJECT_ID" --quiet 2>/dev/null || true
    }

    print_info "Storing Supabase credentials in Secret Manager..."
    _upsert_secret "$URL_SECRET_NAME" "$SUPABASE_URL"
    _upsert_secret "$KEY_SECRET_NAME" "$SERVICE_ROLE_KEY"
    _upsert_secret "$JWT_SECRET_NAME" "$JWT_SECRET"
    _upsert_secret "$PG_SECRET_NAME" "$PG_PASSWORD"
    print_success "Secrets stored: $URL_SECRET_NAME, $KEY_SECRET_NAME, $JWT_SECRET_NAME, $PG_SECRET_NAME"

    # ── Also create K8s secrets in app namespaces for wiring ────────────────
    if kubectl get namespace mem-dog &>/dev/null; then
        kubectl -n mem-dog create secret generic api-supabase-secrets \
            --from-literal=SUPABASE_URL="$SUPABASE_URL" \
            --from-literal=SUPABASE_KEY="$SERVICE_ROLE_KEY" \
            --from-literal=STORAGE_BACKEND="supabase" \
            --dry-run=client -o yaml | kubectl apply -f -
        print_success "Created api-supabase-secrets in mem-dog namespace"
    fi

    if kubectl get namespace webhook-gateway &>/dev/null; then
        kubectl -n webhook-gateway create secret generic ocg-supabase-secrets \
            --from-literal=SUPABASE_URL="$SUPABASE_URL" \
            --from-literal=SUPABASE_KEY="$SERVICE_ROLE_KEY" \
            --dry-run=client -o yaml | kubectl apply -f -
        print_success "Created ocg-supabase-secrets in webhook-gateway namespace"
    fi

    # ── Print summary ──────────────────────────────────────────────────────
    print_header "Supabase Deployed to GKE"
    echo "Project:           $PROJECT_ID"
    echo "Cluster:           $GKE_CLUSTER"
    echo "Namespace:         supabase"
    echo ""
    echo "Kong (API GW):     $SUPABASE_URL"
    echo "PostgREST:         http://supabase-rest.supabase.svc.cluster.local:3000"
    echo "Auth (GoTrue):     http://supabase-auth.supabase.svc.cluster.local:9999"
    echo "Realtime:          http://supabase-realtime.supabase.svc.cluster.local:4000"
    echo "Meta:              http://supabase-meta.supabase.svc.cluster.local:8080"
    echo "Studio:            http://supabase-studio.supabase.svc.cluster.local:3000"
    echo ""
    echo "Next steps — activate Supabase for the API:"
    echo ""
    echo "  GKE API (in-cluster):"
    echo "    kubectl patch configmap api-config -n mem-dog -p '{\"data\":{\"STORAGE_BACKEND\":\"supabase\"}}'"
    echo "    kubectl set env deployment/api -n mem-dog --from=secret/api-supabase-secrets"
    echo "    kubectl rollout restart deployment/api -n mem-dog"
    echo ""
    echo "  Cloud Run API:"
    echo "    USE_SUPABASE_STORAGE=true $0 deploy-api -p $PROJECT_ID -e $ENVIRONMENT"
    echo ""
    echo "  OpenClaw direct reads (optional):"
    echo "    kubectl set env deployment/webhook-gateway -n webhook-gateway --from=secret/ocg-supabase-secrets"
    echo "    kubectl rollout restart deployment/webhook-gateway -n webhook-gateway"
    echo ""
    echo "  Verify:   kubectl get pods -n supabase"
    echo "  Studio:   kubectl port-forward svc/supabase-studio -n supabase 3000:3000"
    echo "  Re-seed:  $0 seed-supabase-gke -p $PROJECT_ID -e $ENVIRONMENT"
    echo "  Revert:   kubectl patch configmap api-config -n mem-dog -p '{\"data\":{\"STORAGE_BACKEND\":\"gcs\"}}'"
    echo ""
}

# =============================================================================
# Seed Supabase GKE (re-run schema seed job)
# =============================================================================

seed_supabase_gke() {
    print_header "Seeding Supabase on GKE: $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        print_error "--project is required"
        exit 1
    fi

    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"
    K8S_DIR="$ROOT_DIR/k8s/supabase"

    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --region "$REGION" --project "$PROJECT_ID" 2>/dev/null || {
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        }
    fi

    print_info "Applying seed ConfigMap..."
    kubectl apply -f "$K8S_DIR/seed-configmap.yaml"

    print_info "Re-running seed job..."
    kubectl delete job supabase-seed -n supabase --ignore-not-found
    kubectl apply -f "$K8S_DIR/seed-job.yaml"
    kubectl wait --for=condition=complete job/supabase-seed -n supabase --timeout=120s

    print_success "Seed complete. Tables and functions are up to date."
}

# =============================================================================
# Destroy Supabase data on GKE (wipe tables, keep environment)
# =============================================================================

destroy_supabase_data_gke() {
    print_header "Destroying Supabase data on GKE: $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        print_error "--project is required"
        exit 1
    fi

    if [ -z "${CONFIRM:-}" ]; then
        print_error "Add --confirm to destroy Supabase data (e.g. $0 destroy-supabase-data-gke -p $PROJECT_ID -e $ENVIRONMENT --confirm)"
        exit 1
    fi

    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --region "$REGION" --project "$PROJECT_ID" 2>/dev/null || {
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        }
    fi

    _supa_psql() {
        kubectl exec -i -n supabase supabase-db-0 -c postgres -- \
            psql -U postgres -d postgres "$@"
    }

    if ! _supa_psql -c "SELECT 1;" &>/dev/null; then
        print_error "Cannot reach Supabase DB pod. Ensure Supabase is running."
        exit 1
    fi

    print_info "Deleting mem_dog_blobs (preserving users store)..."
    _supa_psql -c "DELETE FROM mem_dog_blobs WHERE store_name != 'users';" &>/dev/null \
        && print_success "mem_dog_blobs wiped (users preserved)" \
        || print_warning "mem_dog_blobs wipe failed (table may not exist)"

    print_info "Truncating mem_dog_embeddings..."
    _supa_psql -c "TRUNCATE mem_dog_embeddings;" &>/dev/null \
        && print_success "mem_dog_embeddings truncated" \
        || print_warning "mem_dog_embeddings truncate failed (table may not exist)"

    print_info "Truncating store_kv..."
    _supa_psql -c "TRUNCATE store_kv;" &>/dev/null \
        && print_success "store_kv truncated" \
        || print_warning "store_kv truncate failed (table may not exist)"

    echo ""
    print_success "Supabase data destroyed for $ENVIRONMENT."
}

# =============================================================================
# Destroy Supabase environment on GKE (delete entire namespace)
# =============================================================================

destroy_supabase_gke() {
    print_header "Destroying Supabase environment on GKE: $ENVIRONMENT"

    if [ -z "$PROJECT_ID" ]; then
        print_error "--project is required"
        exit 1
    fi

    if [ -z "${CONFIRM:-}" ]; then
        print_error "Add --confirm to destroy Supabase environment (e.g. $0 destroy-supabase-gke -p $PROJECT_ID -e $ENVIRONMENT --confirm)"
        exit 1
    fi

    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --region "$REGION" --project "$PROJECT_ID" 2>/dev/null || {
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        }
    fi

    print_info "Deleting supabase namespace (all resources)..."
    if kubectl get namespace supabase &>/dev/null; then
        kubectl delete namespace supabase --timeout=120s
        print_success "Namespace supabase deleted"
    else
        print_warning "Namespace supabase not found (already deleted?)"
    fi

    # Clean up api-supabase-secrets in mem-dog namespace
    if kubectl get secret api-supabase-secrets -n mem-dog &>/dev/null 2>&1; then
        kubectl delete secret api-supabase-secrets -n mem-dog
        print_success "Deleted api-supabase-secrets from mem-dog namespace"
    fi

    # Clean up ocg-supabase-secrets in webhook-gateway namespace
    if kubectl get secret ocg-supabase-secrets -n webhook-gateway &>/dev/null 2>&1; then
        kubectl delete secret ocg-supabase-secrets -n webhook-gateway
        print_success "Deleted ocg-supabase-secrets from webhook-gateway namespace"
    fi

    # Optionally delete Secret Manager secrets
    if [ -n "${DELETE_SECRETS:-}" ]; then
        local URL_SECRET="mem-dog-supabase-url-${ENVIRONMENT}"
        local KEY_SECRET="mem-dog-supabase-key-${ENVIRONMENT}"

        for secret_name in "$URL_SECRET" "$KEY_SECRET"; do
            if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
                gcloud secrets delete "$secret_name" --project="$PROJECT_ID" --quiet
                print_success "Deleted secret: $secret_name"
            else
                print_warning "Not found (skip): $secret_name"
            fi
        done
    else
        print_info "Secret Manager secrets preserved. Use --delete-secrets to remove them."
    fi

    echo ""
    print_success "Supabase environment destroyed for $ENVIRONMENT in $PROJECT_ID."
    echo ""
}


# =============================================================================
# Setup Environment
# =============================================================================

setup_env() {
    print_header "Setting Up Environment: $ENVIRONMENT"
    
    # Enable APIs
    print_info "Enabling required APIs..."
    gcloud services enable \
        cloudresourcemanager.googleapis.com \
        serviceusage.googleapis.com \
        storage.googleapis.com \
        run.googleapis.com \
        artifactregistry.googleapis.com \
        iam.googleapis.com \
        iamcredentials.googleapis.com \
        compute.googleapis.com \
        --project="$PROJECT_ID"
    print_success "APIs enabled"
    
    # Create Artifact Registry
    print_info "Creating Artifact Registry..."
    if ! gcloud artifacts repositories describe mem-dog --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        gcloud artifacts repositories create mem-dog \
            --repository-format=docker \
            --location="$REGION" \
            --description="Docker repository for mem-dog services" \
            --project="$PROJECT_ID"
        print_success "Artifact Registry created"
    else
        print_warning "Artifact Registry already exists"
    fi
    
    # Create Cloud Run Service Account
    CLOUD_RUN_SA="mem-dog-cloud-run-${ENVIRONMENT}"
    SA_EMAIL="${CLOUD_RUN_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
    
    print_info "Creating Cloud Run Service Account..."
    if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        gcloud iam service-accounts create "$CLOUD_RUN_SA" \
            --display-name="Service Account for mem-dog Cloud Run services ($ENVIRONMENT)" \
            --description="Used by API and UI Cloud Run services to access GCS in $ENVIRONMENT" \
            --project="$PROJECT_ID"
        print_success "Service Account created: $SA_EMAIL"
    else
        print_warning "Service Account already exists"
    fi
    
    # Create GCS Buckets (Core)
    print_info "Creating Core GCS Buckets..."
    # "index" is the reverse-index bucket added for multitenancy (user/data/memory search).
    CORE_BUCKETS=("raw" "meta" "memories" "users" "index")
    for bucket_suffix in "${CORE_BUCKETS[@]}"; do
        BUCKET_NAME="${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
        if ! gcloud storage buckets describe "gs://$BUCKET_NAME" &>/dev/null; then
            gcloud storage buckets create "gs://$BUCKET_NAME" \
                --location="$REGION" \
                --project="$PROJECT_ID" \
                --uniform-bucket-level-access
            gcloud storage buckets update "gs://$BUCKET_NAME" --versioning
            gcloud storage buckets update "gs://$BUCKET_NAME" \
                --update-labels="environment=$ENVIRONMENT,purpose=${bucket_suffix}-storage"
            print_success "Bucket created: $BUCKET_NAME"
        else
            print_warning "Bucket already exists: $BUCKET_NAME"
        fi
    done
    
    # Create GCS Buckets (AI Layer)
    print_info "Creating AI Layer GCS Buckets..."
    AI_BUCKETS=("prompts" "embeddings" "viewpoints" "aiconfig" "skills" "stats")
    # Optional: channels bucket for per-channel metadata (when set, API uses it; else uses meta bucket prefix)
    OPTIONAL_BUCKETS=("channels")
    for bucket_suffix in "${AI_BUCKETS[@]}"; do
        BUCKET_NAME="${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
        if ! gcloud storage buckets describe "gs://$BUCKET_NAME" &>/dev/null; then
            gcloud storage buckets create "gs://$BUCKET_NAME" \
                --location="$REGION" \
                --project="$PROJECT_ID" \
                --uniform-bucket-level-access
            gcloud storage buckets update "gs://$BUCKET_NAME" --versioning
            gcloud storage buckets update "gs://$BUCKET_NAME" \
                --update-labels="environment=$ENVIRONMENT,purpose=ai-${bucket_suffix}-storage"
            print_success "AI Bucket created: $BUCKET_NAME"
        else
            print_warning "AI Bucket already exists: $BUCKET_NAME"
        fi
    done
    for bucket_suffix in "${OPTIONAL_BUCKETS[@]}"; do
        BUCKET_NAME="${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
        if ! gcloud storage buckets describe "gs://$BUCKET_NAME" &>/dev/null; then
            gcloud storage buckets create "gs://$BUCKET_NAME" \
                --location="$REGION" \
                --project="$PROJECT_ID" \
                --uniform-bucket-level-access
            gcloud storage buckets update "gs://$BUCKET_NAME" --versioning
            gcloud storage buckets update "gs://$BUCKET_NAME" \
                --update-labels="environment=$ENVIRONMENT,purpose=${bucket_suffix}-storage"
            print_success "Bucket created: $BUCKET_NAME"
        else
            print_warning "Bucket already exists: $BUCKET_NAME"
        fi
    done
    
    # Create System Config Bucket
    print_info "Creating System Config Bucket..."
    SYSCONFIG_BUCKET="${PROJECT_ID}-mem-dog-sysconfig-${ENVIRONMENT}"
    if ! gcloud storage buckets describe "gs://$SYSCONFIG_BUCKET" &>/dev/null; then
        gcloud storage buckets create "gs://$SYSCONFIG_BUCKET" \
            --location="$REGION" \
            --project="$PROJECT_ID" \
            --uniform-bucket-level-access
        gcloud storage buckets update "gs://$SYSCONFIG_BUCKET" --versioning
        gcloud storage buckets update "gs://$SYSCONFIG_BUCKET" \
            --update-labels="environment=$ENVIRONMENT,purpose=system-config"
        print_success "System Config Bucket created: $SYSCONFIG_BUCKET"
    else
        print_warning "System Config Bucket already exists: $SYSCONFIG_BUCKET"
    fi
    
    # Configure IAM for all buckets (Core + AI + Optional + Sysconfig)
    print_info "Configuring IAM for all buckets..."
    ALL_BUCKETS=("${CORE_BUCKETS[@]}" "${AI_BUCKETS[@]}" "${OPTIONAL_BUCKETS[@]}")
    for bucket_suffix in "${ALL_BUCKETS[@]}"; do
        BUCKET_NAME="${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
        gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_NAME" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/storage.objectAdmin" \
            --quiet
    done
    gcloud storage buckets add-iam-policy-binding "gs://$SYSCONFIG_BUCKET" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/storage.objectViewer" \
        --quiet
    print_success "IAM configured for all buckets"
    
    # Generate and upload platform-config.json
    print_info "Generating platform-config.json..."
    MEMORIES_BUCKET_NAME="${PROJECT_ID}-mem-dog-memories-${ENVIRONMENT}"
    CONFIG_JSON=$(cat <<EOCFG
{
  "version": "1",
  "environment": "$ENVIRONMENT",
  "gcp_project_id": "$PROJECT_ID",
  "buckets": {
    "raw": "${PROJECT_ID}-mem-dog-raw-${ENVIRONMENT}",
    "meta": "${PROJECT_ID}-mem-dog-meta-${ENVIRONMENT}",
    "memories": "${MEMORIES_BUCKET_NAME}",
    "users": "${PROJECT_ID}-mem-dog-users-${ENVIRONMENT}",
    "prompts": "${PROJECT_ID}-mem-dog-prompts-${ENVIRONMENT}",
    "embeddings": "${PROJECT_ID}-mem-dog-embeddings-${ENVIRONMENT}",
    "viewpoints": "${PROJECT_ID}-mem-dog-viewpoints-${ENVIRONMENT}",
    "ai_config": "${PROJECT_ID}-mem-dog-aiconfig-${ENVIRONMENT}",
    "skills": "${PROJECT_ID}-mem-dog-skills-${ENVIRONMENT}",
    "stats": "${PROJECT_ID}-mem-dog-stats-${ENVIRONMENT}",
    "index": "${PROJECT_ID}-mem-dog-index-${ENVIRONMENT}",
    "channels": "${PROJECT_ID}-mem-dog-channels-${ENVIRONMENT}"
  },
  "ai": {
    "system_gemini_api_key": "",
    "system_gemini_model_embedding": "text-embedding-004",
    "system_gemini_model_completion": "gemini-1.5-flash",
    "ollama_cloud_api_key": "",
    "ai_encryption_key": ""
  },
  "telemetry": {
    "otel_enabled": true,
    "otel_service_name": "mem-dog-api",
    "otel_exporter_otlp_endpoint": "",
    "otel_exporter_otlp_protocol": "grpc"
  },
  "app": {
    "log_level": "INFO",
    "default_user": "${DEFAULT_USER:-demo}",
    "system_user_id": "${SYSTEM_USER_ID:-${DEFAULT_USER:-demo}}",
    "app_version": "${APP_VERSION:-0.1.0}"
  }
}
EOCFG
)
    echo "$CONFIG_JSON" | gcloud storage cp - "gs://${SYSCONFIG_BUCKET}/platform-config.json" \
        --content-type="application/json"
    print_success "platform-config.json uploaded to gs://${SYSCONFIG_BUCKET}/"
    
    # Configure Docker auth
    print_info "Configuring Docker for Artifact Registry..."
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
    print_success "Docker configured"
    
    print_header "Environment Setup Complete"
    echo "Project ID:     $PROJECT_ID"
    echo "Region:         $REGION"
    echo "Environment:    $ENVIRONMENT"
    echo "Service Account: $SA_EMAIL"
    echo ""
    echo "System Config Bucket:"
    echo "  - $SYSCONFIG_BUCKET"
    echo ""
    echo "Core Buckets created:"
    for bucket_suffix in "${CORE_BUCKETS[@]}"; do
        echo "  - ${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
    done
    echo ""
    echo "AI Layer Buckets created:"
    for bucket_suffix in "${AI_BUCKETS[@]}"; do
        echo "  - ${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
    done
    echo "Optional Buckets created:"
    for bucket_suffix in "${OPTIONAL_BUCKETS[@]}"; do
        echo "  - ${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
    done
}

# =============================================================================
# Deploy API
# =============================================================================

deploy_api() {
    print_header "Deploying API"
    
    SERVICE_NAME="mem-dog-api"
    SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/api:${ENVIRONMENT}-latest"
    SYSCONFIG_BUCKET="${PROJECT_ID}-mem-dog-sysconfig-${ENVIRONMENT}"
    
    # Build (explicitly for linux/amd64 to ensure Cloud Run compatibility)
    print_info "Building API Docker image for linux/amd64..."
    cd "$ROOT_DIR/api"
    docker buildx build --no-cache --platform linux/amd64 -t "$IMAGE_TAG" --load .
    print_success "API image built"
    
    # Push
    print_info "Pushing API image to Artifact Registry..."
    docker push "$IMAGE_TAG"
    print_success "API image pushed"
    
    # Deploy — the API reads bucket names from platform-config.json in the
    # system config bucket.  Only bootstrap env vars are needed here.
    # Use --update-env-vars so any vars already on the service (e.g.
    # MODEL_SERVER_URL set from a previous deploy) are preserved.
    ENV_VARS="GCP_PROJECT_ID=$PROJECT_ID,SYSTEM_CONFIG_BUCKET=$SYSCONFIG_BUCKET,ENVIRONMENT=$ENVIRONMENT"

    # ── Multitenancy / versioning env vars ─────────────────────────────────
    # SYSTEM_USER_ID: used for pipeline-level telemetry spans (default: DEFAULT_USER or "demo")
    # APP_VERSION:    embedded in telemetry spans and device provenance metadata
    # INDEX_BUCKET:   dedicated reverse-index bucket created by setup-env ("index" suffix)
    #                 Leave blank to fall back to writing _idx/ entries inside META_BUCKET.
    _SYSTEM_USER="${SYSTEM_USER_ID:-${DEFAULT_USER:-demo}}"
    _APP_VERSION="${APP_VERSION:-0.1.0}"
    _INDEX_BUCKET="${INDEX_BUCKET:-${PROJECT_ID}-mem-dog-index-${ENVIRONMENT}}"
    ENV_VARS="$ENV_VARS,SYSTEM_USER_ID=$_SYSTEM_USER,APP_VERSION=$_APP_VERSION,INDEX_BUCKET=$_INDEX_BUCKET"
    print_success "Multitenancy vars — SYSTEM_USER_ID=$_SYSTEM_USER, APP_VERSION=$_APP_VERSION, INDEX_BUCKET=$_INDEX_BUCKET"

    # ── Legacy single model server (webhook pipeline) ───────────────────────
    if [ -n "${MODEL_SERVER_URL:-}" ]; then
        ENV_VARS="$ENV_VARS,MODEL_SERVER_URL=$MODEL_SERVER_URL"
        print_success "Model server URL: $MODEL_SERVER_URL"
    fi
    if [ -n "${MODEL_SERVER_MODEL:-}" ]; then
        ENV_VARS="$ENV_VARS,MODEL_SERVER_MODEL=$MODEL_SERVER_MODEL"
    fi
    if [ -n "${MODEL_SERVER_TIMEOUT_S:-}" ]; then
        ENV_VARS="$ENV_VARS,MODEL_SERVER_TIMEOUT_S=$MODEL_SERVER_TIMEOUT_S"
    fi
    if [ -n "${OLLAMA_TIER:-}" ]; then
        ENV_VARS="$ENV_VARS,OLLAMA_TIER=$OLLAMA_TIER"
        print_success "OLLAMA_TIER=$OLLAMA_TIER (tier model servers use Ollama)"
    fi

    # ── AI Chat multi-tier model servers ────────────────────────────────────
    # Model servers are added manually (no auto-detection). Only wire tier URLs when
    # explicitly set via MODEL_SERVER_URL_SMALL, MODEL_SERVER_URL_MEDIUM, etc.
    MODELS_BUCKET="${PROJECT_ID}-mem-dog-models-${ENVIRONMENT}"

    if gcloud storage buckets describe "gs://$MODELS_BUCKET" --project="$PROJECT_ID" &>/dev/null; then
        ENV_VARS="$ENV_VARS,DEPLOYMENT_MODE=cloud,GCS_MODELS_BUCKET=$MODELS_BUCKET"
        print_success "Models bucket found: $MODELS_BUCKET — DEPLOYMENT_MODE=cloud"

        TIER_URLS=()
        for TIER in small medium large very-large; do
            TIER_UPPER=$(echo "$TIER" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
            VARNAME_URL="MODEL_SERVER_URL_${TIER_UPPER}"
            VARNAME_SVC="MODEL_SERVER_SERVICE_${TIER_UPPER}"
            TIER_SVC="mem-dog-model-server-${TIER}-${ENVIRONMENT}"
            # Only use explicitly provided URLs (no auto-detection from Cloud Run).
            URL_VAL="${!VARNAME_URL:-}"
            if [ -n "$URL_VAL" ]; then
                ENV_VARS="$ENV_VARS,${VARNAME_URL}=${URL_VAL},${VARNAME_SVC}=${TIER_SVC}"
                TIER_URLS+=("$TIER=$URL_VAL")
                print_success "Tier ${TIER}: ${URL_VAL} (from env)"
            fi
        done

        # Write tier machines to AI config bucket only when explicitly provided.
        if [ ${#TIER_URLS[@]} -gt 0 ]; then
            print_info "Writing tier machines to AI config bucket..."
            write_tier_machines_to_ai_config
        fi

        # Ensure the API SA can manage tier Cloud Run services (for activation).
        SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
        print_info "Granting roles/run.developer to API SA for model activation..."
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/run.developer" --quiet 2>/dev/null || true
        print_success "roles/run.developer granted (or already present)"

        print_info "Granting roles/iam.serviceAccountUser to API SA (needed to act as itself)..."
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/iam.serviceAccountUser" --quiet 2>/dev/null || true
        print_success "roles/iam.serviceAccountUser granted"

        print_info "Granting roles/artifactregistry.reader to API SA (needed to re-deploy tiers)..."
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/artifactregistry.reader" --quiet 2>/dev/null || true
        print_success "roles/artifactregistry.reader granted"

        # Grant API SA read access to the models bucket so is_available() and
        # reconcile-status can check which GGUFs are present.
        print_info "Granting roles/storage.objectViewer on models bucket to API SA..."
        gcloud storage buckets add-iam-policy-binding "gs://$MODELS_BUCKET" \
            --project="$PROJECT_ID" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/storage.objectViewer" --quiet 2>/dev/null || true
        print_success "storage.objectViewer granted on $MODELS_BUCKET"
    fi

    if [ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]; then
        ENV_VARS="$ENV_VARS,HUGGING_FACE_HUB_TOKEN=$HUGGING_FACE_HUB_TOKEN"
        print_success "HUGGING_FACE_HUB_TOKEN included"
    fi

    # ── Encryption key for LLM API keys ─────────────────────────────────────
    if [ -n "${MASTER_ENCRYPTION_KEY:-}" ]; then
        ENV_VARS="$ENV_VARS,MASTER_ENCRYPTION_KEY=$MASTER_ENCRYPTION_KEY"
        print_success "MASTER_ENCRYPTION_KEY included (for LLM API key encryption)"
    else
        print_warning "MASTER_ENCRYPTION_KEY not set — LLM features will be unavailable"
        print_info "Generate one with: python -c \"import base64, os; print(base64.b64encode(os.urandom(32)).decode())\""
    fi

    # Auto-wire Download Topic if it exists.
    DOWNLOAD_TOPIC="mem-dog-downloads-${ENVIRONMENT}"
    if gcloud pubsub topics describe "$DOWNLOAD_TOPIC" --project="$PROJECT_ID" &>/dev/null; then
        ENV_VARS="$ENV_VARS,DOWNLOAD_TOPIC=$DOWNLOAD_TOPIC"
        print_success "DOWNLOAD_TOPIC wired: $DOWNLOAD_TOPIC"
        
        # Grant API SA publisher permission
        gcloud pubsub topics add-iam-policy-binding "$DOWNLOAD_TOPIC" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/pubsub.publisher" --project="$PROJECT_ID" --quiet &>/dev/null || true
        print_success "roles/pubsub.publisher granted on download topic"
    fi

    # ── Wire webhook API Gateway URL and key (when webhook is deployed) ───────
    GATEWAY_NAME="mem-dog-webhook-gw-${ENVIRONMENT}"
    if [ -n "${MEM_DOG_WEBHOOK_GATEWAY_URL:-}" ]; then
        WEBHOOK_GW_URL="$MEM_DOG_WEBHOOK_GATEWAY_URL"
        print_success "Using MEM_DOG_WEBHOOK_GATEWAY_URL from environment"
    elif gcloud api-gateway gateways describe "$GATEWAY_NAME" \
        --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        GW_HOST=$(gcloud api-gateway gateways describe "$GATEWAY_NAME" \
            --location="$REGION" --project="$PROJECT_ID" \
            --format='value(defaultHostname)')
        WEBHOOK_GW_URL="https://${GW_HOST}/webhook"
        print_success "Auto-detected webhook gateway URL"
    fi
    if [ -n "${WEBHOOK_GW_URL:-}" ]; then
        ENV_VARS="$ENV_VARS,WEBHOOK_GATEWAY_URL=$WEBHOOK_GW_URL"
        print_success "WEBHOOK_GATEWAY_URL wired: $WEBHOOK_GW_URL"
        if [ -n "${MEM_DOG_WEBHOOK_API_KEY:-}" ]; then
            ENV_VARS="$ENV_VARS,WEBHOOK_API_KEY=$MEM_DOG_WEBHOOK_API_KEY"
            print_success "WEBHOOK_API_KEY wired"
        else
            print_info "Set MEM_DOG_WEBHOOK_API_KEY and re-run deploy-api to wire WEBHOOK_API_KEY"
        fi
    fi

    # ── Wire Postgres storage (only if USE_POSTGRES_STORAGE=true) ─────────────
    local INSTANCE_NAME="mem-dog-pg-${ENVIRONMENT}"
    local SECRET_NAME="mem-dog-postgres-url-${ENVIRONMENT}"
    local CLOUD_SQL_FLAGS=""
    local SECRET_FLAGS=""

    if [ "$USE_POSTGRES_STORAGE" = "true" ]; then
        if gcloud sql instances describe "$INSTANCE_NAME" \
                --project="$PROJECT_ID" &>/dev/null; then
            local CONNECTION_NAME="${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"
            CLOUD_SQL_FLAGS="--add-cloudsql-instances=${CONNECTION_NAME}"
            SECRET_FLAGS="--update-secrets=POSTGRES_URL=${SECRET_NAME}:latest"
            print_success "Postgres storage enabled — wiring POSTGRES_URL"
        else
            print_warning "USE_POSTGRES_STORAGE=true but Cloud SQL instance $INSTANCE_NAME not found — run setup-postgres first"
        fi
    else
        print_info "Postgres storage not requested (USE_POSTGRES_STORAGE=$USE_POSTGRES_STORAGE)"
    fi

    # ── Wire Redis storage (only if USE_REDIS_STORAGE=true) ─────────────────
    local REDIS_SECRET_NAME="mem-dog-redis-url-${ENVIRONMENT}"
    local REDIS_VPC_SECRET_NAME="mem-dog-redis-vpc-${ENVIRONMENT}"
    local VPC_FLAGS=""
    if [ "$USE_REDIS_STORAGE" = "true" ]; then
        if gcloud secrets describe "$REDIS_SECRET_NAME" \
                --project="$PROJECT_ID" &>/dev/null; then
            if [ -n "$SECRET_FLAGS" ]; then
                SECRET_FLAGS="${SECRET_FLAGS},REDIS_URL=${REDIS_SECRET_NAME}:latest"
            else
                SECRET_FLAGS="--update-secrets=REDIS_URL=${REDIS_SECRET_NAME}:latest"
            fi
            print_success "Redis storage enabled — wiring REDIS_URL"
            # Memorystore needs Direct VPC egress; Cloud Run must use --network and --subnet
            if gcloud secrets describe "$REDIS_VPC_SECRET_NAME" \
                    --project="$PROJECT_ID" &>/dev/null; then
                VPC_FLAGS="--network=default --subnet=${REGION}/default"
                print_success "Redis uses Memorystore — wiring Direct VPC egress"
            fi
        else
            print_warning "USE_REDIS_STORAGE=true but secret $REDIS_SECRET_NAME not found — run setup-redis or deploy-redis first"
        fi
    else
        print_info "Redis storage not requested (USE_REDIS_STORAGE=$USE_REDIS_STORAGE)"
    fi

    # ── Wire Supabase (only if USE_SUPABASE_STORAGE=true) ─────────────────────
    local SUPABASE_URL_SECRET="mem-dog-supabase-url-${ENVIRONMENT}"
    local SUPABASE_KEY_SECRET="mem-dog-supabase-key-${ENVIRONMENT}"
    if [ "$USE_SUPABASE_STORAGE" = "true" ]; then
        if gcloud secrets describe "$SUPABASE_URL_SECRET" --project="$PROJECT_ID" &>/dev/null && \
           gcloud secrets describe "$SUPABASE_KEY_SECRET" --project="$PROJECT_ID" &>/dev/null; then
            local SUPABASE_SECRETS="SUPABASE_URL=${SUPABASE_URL_SECRET}:latest,SUPABASE_KEY=${SUPABASE_KEY_SECRET}:latest"
            print_success "Supabase storage enabled — wiring SUPABASE_URL, SUPABASE_KEY, STORAGE_BACKEND=supabase"
            if [ -n "$SECRET_FLAGS" ]; then
                SECRET_FLAGS="${SECRET_FLAGS},${SUPABASE_SECRETS}"
            else
                SECRET_FLAGS="--update-secrets=${SUPABASE_SECRETS}"
            fi
            ENV_VARS="${ENV_VARS},STORAGE_BACKEND=supabase"
        else
            print_warning "USE_SUPABASE_STORAGE=true but $SUPABASE_URL_SECRET or $SUPABASE_KEY_SECRET not found — run setup-supabase first"
        fi
    else
        print_info "Supabase store not requested (USE_SUPABASE_STORAGE=$USE_SUPABASE_STORAGE)"
    fi

    print_info "Deploying API to Cloud Run..."
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --platform managed \
        --allow-unauthenticated \
        --service-account "$SA_EMAIL" \
        --update-env-vars "$ENV_VARS" \
        ${CLOUD_SQL_FLAGS:+"$CLOUD_SQL_FLAGS"} \
        ${VPC_FLAGS:+"$VPC_FLAGS"} \
        ${SECRET_FLAGS:+"$SECRET_FLAGS"}

    # Get URL
    API_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --format 'value(status.url)')
    
    print_success "API deployed successfully!"
    echo ""
    echo "API URL: $API_URL"
    echo "System Config: gs://$SYSCONFIG_BUCKET/platform-config.json"
    echo ""
    echo "📌 To enable System Default AI (Gemini), update platform-config.json"
    echo "   or set the env var directly:"
    echo "   gcloud run services update $SERVICE_NAME \\"
    echo "     --region $REGION --project $PROJECT_ID \\"
    echo "     --set-env-vars SYSTEM_GEMINI_API_KEY=your-gemini-api-key"
    echo ""
    echo "   Get a Gemini API key from: https://aistudio.google.com/app/apikey"
}

# =============================================================================
# Deploy UI
# =============================================================================

deploy_ui() {
    local READ_ONLY="${UI_READ_ONLY:-false}"
    if [ "$READ_ONLY" = "true" ]; then
        print_header "Deploying Read-Only UI"
    else
        print_header "Deploying UI"
    fi

    if [ "$READ_ONLY" = "true" ]; then
        SERVICE_NAME="mem-dog-ui-read-${ENVIRONMENT}"
    else
        SERVICE_NAME="mem-dog-ui-${ENVIRONMENT}"
    fi
    API_SERVICE_NAME="mem-dog-api"
    SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    if [ "$READ_ONLY" = "true" ]; then
        IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/ui-read:${ENVIRONMENT}-latest"
    else
        IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/ui:${ENVIRONMENT}-latest"
    fi
    
    # Get API URL (override → GKE Gateway → Cloud Run project-number → gcloud)
    if [ -n "${MEM_DOG_API_URL:-}" ]; then
        API_URL="$MEM_DOG_API_URL"
        print_success "Using MEM_DOG_API_URL from environment: $API_URL"
    else
        API_URL=""
        # Try GKE Gateway (open-jaws) — API exposed at /gke-api via HTTPRoute
        GKE_GW_IP=$(kubectl get gateway open-jaws -n webhook-gateway \
            -o jsonpath='{.status.addresses[0].value}' 2>/dev/null || echo "")
        if [ -n "$GKE_GW_IP" ]; then
            API_URL="http://${GKE_GW_IP}/gke-api"
            print_success "Using GKE Gateway API URL: $API_URL"
        fi
        # Fallback: Cloud Run API
        if [ -z "$API_URL" ]; then
            print_info "Getting Cloud Run API URL..."
            PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)' 2>/dev/null || echo "")
            if [ -n "$PROJECT_NUMBER" ]; then
                API_URL="https://mem-dog-api-${PROJECT_NUMBER}.${REGION}.run.app"
                print_success "Using project-number API URL: $API_URL"
            else
                API_URL=$(gcloud run services describe "$API_SERVICE_NAME" \
                    --region "$REGION" \
                    --project "$PROJECT_ID" \
                    --format 'value(status.url)' 2>/dev/null || echo "")
            fi
        fi
        if [ -z "$API_URL" ]; then
            print_error "API service not found (no GKE Gateway, no Cloud Run API)."
            echo ""
            echo "Provide the URL manually:"
            echo "  MEM_DOG_API_URL=https://your-api-url $0 deploy-ui -p $PROJECT_ID -e $ENVIRONMENT"
            exit 1
        fi
    fi

    # Resolve API key (for GKE deployments with api-auth-secret)
    UI_API_KEY="${NEXT_PUBLIC_API_KEY:-${MEM_DOG_API_KEY:-}}"
    if [ -z "$UI_API_KEY" ]; then
        UI_API_KEY=$(kubectl get secret api-auth-secret -n mem-dog \
            -o jsonpath='{.data.API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        if [ -n "$UI_API_KEY" ]; then
            print_success "API key read from api-auth-secret in mem-dog namespace"
        fi
    fi

    # Get webhook gateway URL for Testing tab (optional)
    WEBHOOK_GATEWAY_URL="${MEM_DOG_WEBHOOK_GATEWAY_URL:-}"
    if [ -z "$WEBHOOK_GATEWAY_URL" ]; then
        GATEWAY_NAME="mem-dog-webhook-gw-${ENVIRONMENT}"
        if gcloud api-gateway gateways describe "$GATEWAY_NAME" \
            --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
            GW_HOST=$(gcloud api-gateway gateways describe "$GATEWAY_NAME" \
                --location="$REGION" --project="$PROJECT_ID" \
                --format='value(defaultHostname)')
            WEBHOOK_GATEWAY_URL="https://${GW_HOST}/webhook"
            print_success "Using webhook gateway URL: $WEBHOOK_GATEWAY_URL"
        fi
    else
        print_success "Using MEM_DOG_WEBHOOK_GATEWAY_URL from environment"
    fi
    WEBHOOK_API_KEY="${MEM_DOG_WEBHOOK_API_KEY:-}"

    # Generate package-lock.json if missing
    cd "$ROOT_DIR/ui"
    if [ ! -f "package-lock.json" ]; then
        print_info "Generating package-lock.json..."
        npm install
        print_success "package-lock.json generated"
    fi
    
    # When the API is on plain HTTP (e.g. GKE Gateway) but the UI will be served
    # over HTTPS (Cloud Run), leave NEXT_PUBLIC_API_URL empty so the browser uses
    # relative paths (/api/v1/...) and the Next.js server-side rewrite proxies to
    # the actual backend via the API_URL build arg.  This avoids mixed-content blocks.
    local CLIENT_API_URL="$API_URL"
    local SERVER_API_URL=""
    if [[ "$API_URL" == http://* ]]; then
        print_info "HTTP API detected — using server-side rewrite proxy (no mixed content)"
        SERVER_API_URL="$API_URL"
        CLIENT_API_URL=""
    fi

    # For read-only mode: skip Supabase keys (anonymous mode) and webhook args
    local BUILD_SUPABASE_URL="${NEXT_PUBLIC_SUPABASE_URL:-}"
    local BUILD_SUPABASE_ANON_KEY="${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}"
    local BUILD_SUPABASE_AUTH_URL="${SUPABASE_AUTH_URL:-}"
    local BUILD_WEBHOOK_URL="${WEBHOOK_GATEWAY_URL:-}"
    local BUILD_WEBHOOK_KEY="${WEBHOOK_API_KEY:-}"
    local BUILD_READ_ONLY=""
    if [ "$READ_ONLY" = "true" ]; then
        BUILD_SUPABASE_URL=""
        BUILD_SUPABASE_ANON_KEY=""
        BUILD_SUPABASE_AUTH_URL=""
        BUILD_WEBHOOK_URL=""
        BUILD_WEBHOOK_KEY=""
        BUILD_READ_ONLY="true"
        print_info "Read-only mode: Supabase auth and webhook args omitted (anonymous access)"
    fi

    # Build (explicitly for linux/amd64 to ensure Cloud Run compatibility)
    print_info "Building UI Docker image for linux/amd64..."
    docker buildx build \
        --no-cache \
        --platform linux/amd64 \
        --build-arg NEXT_PUBLIC_API_URL="$CLIENT_API_URL" \
        --build-arg NEXT_PUBLIC_API_KEY="${UI_API_KEY:-}" \
        --build-arg NEXT_PUBLIC_WEBHOOK_GATEWAY_URL="${BUILD_WEBHOOK_URL}" \
        --build-arg NEXT_PUBLIC_WEBHOOK_API_KEY="${BUILD_WEBHOOK_KEY}" \
        --build-arg NEXT_PUBLIC_SUPABASE_URL="${BUILD_SUPABASE_URL}" \
        --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY="${BUILD_SUPABASE_ANON_KEY}" \
        --build-arg SUPABASE_AUTH_URL="${BUILD_SUPABASE_AUTH_URL}" \
        --build-arg API_URL="${SERVER_API_URL:-}" \
        --build-arg NEXT_PUBLIC_READ_ONLY="${BUILD_READ_ONLY}" \
        -t "$IMAGE_TAG" \
        --load \
        .
    print_success "UI image built"
    
    # Push
    print_info "Pushing UI image to Artifact Registry..."
    docker push "$IMAGE_TAG"
    print_success "UI image pushed"
    
    # Deploy
    print_info "Deploying UI to Cloud Run..."
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --platform managed \
        --allow-unauthenticated \
        --service-account "$SA_EMAIL" \
        --set-env-vars "NEXT_PUBLIC_API_URL=${CLIENT_API_URL},API_URL=${SERVER_API_URL:-},NEXT_PUBLIC_API_KEY=${UI_API_KEY:-}"
    
    # Get URL
    UI_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --format 'value(status.url)')
    
    print_success "UI deployed successfully!"
    echo ""
    echo "UI URL:      $UI_URL"
    echo "API URL:     $API_URL"
    if [ -n "${SERVER_API_URL:-}" ]; then
        echo "  (HTTP API → server-side rewrite proxy, no mixed content)"
    fi
    [ -n "${UI_API_KEY:-}" ] && echo "API Key:     (baked in)"
    if [ -n "$WEBHOOK_GATEWAY_URL" ]; then
        echo "Webhook:     $WEBHOOK_GATEWAY_URL (Testing tab pre-filled)"
        [ -z "$WEBHOOK_API_KEY" ] && echo "             Set MEM_DOG_WEBHOOK_API_KEY and re-deploy to pre-fill API key"
    fi
}

# =============================================================================
# Deploy API (deploy-api-docs is an alias for deploy-api)
# =============================================================================

deploy_api_docs() {
    deploy_api
    print_header "API Deployment Complete!"
    API_URL=$(gcloud run services describe "mem-dog-api" \
        --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
    echo "Environment: $ENVIRONMENT"
    echo "Project:     $PROJECT_ID"
    echo "Region:      $REGION"
    echo ""
    echo "URL: $API_URL"
}

# =============================================================================
# Deploy All
# =============================================================================

deploy_all() {
    setup_env
    deploy_api
    deploy_ui
    
    print_header "Deployment Complete!"
    
    API_URL=$(gcloud run services describe "mem-dog-api" \
        --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
    UI_URL=$(gcloud run services describe "mem-dog-ui-${ENVIRONMENT}" \
        --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
    
    echo "Environment: $ENVIRONMENT"
    echo "Project:     $PROJECT_ID"
    echo "Region:      $REGION"
    echo ""
    echo "URLs:"
    echo "  API:             $API_URL"
    echo "  UI:              $UI_URL"
}

# =============================================================================
# Setup Webhook Infrastructure
# =============================================================================

setup_webhook() {
    print_header "Setting Up Webhook Infrastructure: $ENVIRONMENT"

    TOPIC_NAME="mem-dog-webhook-${ENVIRONMENT}"
    WEBHOOK_SA="mem-dog-webhook-${ENVIRONMENT}"
    WEBHOOK_SA_EMAIL="${WEBHOOK_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

    # Enable webhook APIs
    print_info "Enabling webhook APIs..."
    gcloud services enable \
        cloudfunctions.googleapis.com \
        cloudbuild.googleapis.com \
        pubsub.googleapis.com \
        apigateway.googleapis.com \
        servicecontrol.googleapis.com \
        servicemanagement.googleapis.com \
        run.googleapis.com \
        cloudresourcemanager.googleapis.com \
        cloudtrace.googleapis.com \
        --project="$PROJECT_ID"
    print_success "Webhook APIs enabled"

    # Create Pub/Sub topic
    print_info "Creating Pub/Sub topic..."
    if ! gcloud pubsub topics describe "$TOPIC_NAME" --project="$PROJECT_ID" &>/dev/null; then
        gcloud pubsub topics create "$TOPIC_NAME" \
            --project="$PROJECT_ID" \
            --labels="environment=$ENVIRONMENT,purpose=webhook"
        print_success "Pub/Sub topic created: $TOPIC_NAME"
    else
        print_warning "Pub/Sub topic already exists: $TOPIC_NAME"
    fi

    # Create webhook service account
    print_info "Creating webhook service account..."
    if ! gcloud iam service-accounts describe "$WEBHOOK_SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        gcloud iam service-accounts create "$WEBHOOK_SA" \
            --display-name="Webhook Cloud Functions SA ($ENVIRONMENT)" \
            --description="Used by webhook Cloud Functions for Pub/Sub, API access, and logging" \
            --project="$PROJECT_ID"
        print_success "Service account created: $WEBHOOK_SA_EMAIL"
    else
        print_warning "Service account already exists: $WEBHOOK_SA_EMAIL"
    fi

    # Grant IAM roles
    print_info "Configuring IAM roles..."

    gcloud pubsub topics add-iam-policy-binding "$TOPIC_NAME" \
        --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
        --role="roles/pubsub.publisher" \
        --project="$PROJECT_ID" --quiet
    print_success "Granted pubsub.publisher on topic"

    gcloud pubsub topics add-iam-policy-binding "$TOPIC_NAME" \
        --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
        --role="roles/pubsub.subscriber" \
        --project="$PROJECT_ID" --quiet
    print_success "Granted pubsub.subscriber on topic"

    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
        --role="roles/run.invoker" --quiet
    print_success "Granted run.invoker on project"

    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
        --role="roles/logging.logWriter" --quiet
    print_success "Granted logging.logWriter on project"

    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
        --role="roles/cloudtrace.agent" --quiet
    print_success "Granted cloudtrace.agent on project"

    # Create webhook staging bucket (sub-agents download + persist content here)
    STAGING_BUCKET_NAME="${PROJECT_ID}-mem-dog-webhook-staging-${ENVIRONMENT}"
    print_info "Creating webhook staging bucket: $STAGING_BUCKET_NAME"
    if ! gcloud storage buckets describe "gs://$STAGING_BUCKET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        gcloud storage buckets create "gs://$STAGING_BUCKET_NAME" \
            --location="$REGION" \
            --project="$PROJECT_ID" \
            --uniform-bucket-level-access
        gcloud storage buckets update "gs://$STAGING_BUCKET_NAME" \
            --update-labels="environment=$ENVIRONMENT,purpose=webhook-staging"
        print_success "Webhook staging bucket created: $STAGING_BUCKET_NAME"
    else
        print_warning "Webhook staging bucket already exists: $STAGING_BUCKET_NAME"
    fi

    # Grant webhook SA write access to the staging bucket
    gcloud storage buckets add-iam-policy-binding "gs://$STAGING_BUCKET_NAME" \
        --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
        --role="roles/storage.objectAdmin" \
        --quiet
    print_success "Granted storage.objectAdmin on staging bucket to $WEBHOOK_SA_EMAIL"

    print_header "Webhook Infrastructure Setup Complete"
    echo "Project:          $PROJECT_ID"
    echo "Environment:      $ENVIRONMENT"
    echo "Pub/Sub Topic:    $TOPIC_NAME"
    echo "Service Account:  $WEBHOOK_SA_EMAIL"
    echo "Staging Bucket:   $STAGING_BUCKET_NAME"
    echo ""
    echo "Next step: deploy the webhook pipeline:"
    echo "  $0 deploy-webhook -p $PROJECT_ID -e $ENVIRONMENT"
}

# =============================================================================
# Deploy Model Server to Cloud Run (Cloud Run B)
# =============================================================================

# =============================================================================
# Deploy AI Chat Model Servers — four tiers (small / medium / large / very-large)
# =============================================================================
# Each tier runs Ollama on Cloud Run with GCS FUSE at /models. Re-run deploy-api
# after this so the API picks up the tier URLs.
# =============================================================================

deploy_model_servers_ollama() {
    print_header "Deploying AI Chat Model Servers (Ollama): $ENVIRONMENT"

    SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    OLLAMA_IMAGE="ollama/ollama:latest"
    MODELS_BUCKET="${PROJECT_ID}-mem-dog-models-${ENVIRONMENT}"

    if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        print_error "Service account $SA_EMAIL not found. Run setup-env first."
        exit 1
    fi

    print_info "Enabling required APIs..."
    gcloud services enable run.googleapis.com artifactregistry.googleapis.com --project="$PROJECT_ID"
    print_success "APIs enabled"

    if ! gcloud storage buckets describe "gs://$MODELS_BUCKET" --project="$PROJECT_ID" &>/dev/null; then
        print_info "Creating models bucket gs://$MODELS_BUCKET..."
        gcloud storage buckets create "gs://$MODELS_BUCKET" \
            --location="$REGION" --project="$PROJECT_ID" --uniform-bucket-level-access
        print_success "Bucket created"
    fi

    print_info "Granting bucket IAM to API SA..."
    gcloud storage buckets add-iam-policy-binding "gs://$MODELS_BUCKET" \
        --member="serviceAccount:$SA_EMAIL" --role="roles/storage.objectAdmin" --quiet
    print_success "storage.objectAdmin granted"

    TIER_URLS=()
    TIERS_TO_DEPLOY="${DEPLOY_MODEL_TIERS:-small medium large very-large}"

    for TIER in $TIERS_TO_DEPLOY; do
        TIER_SVC="mem-dog-model-server-${TIER}-${ENVIRONMENT}"
        if get_cloudrun_tier_resources "$TIER"; then
            MEM="${CLOUDRUN_MEM:-6Gi}"
            CPU="${CLOUDRUN_CPU:-2}"
        else
            case "$TIER" in
                small)      MEM="6Gi";  CPU="2" ;;
                medium)     MEM="12Gi"; CPU="4" ;;
                large)      MEM="24Gi"; CPU="8" ;;
                very-large) MEM="80Gi"; CPU="20" ;;
                *)          MEM="6Gi";  CPU="2" ;;
            esac
        fi

        print_info "Deploying tier=$TIER (Ollama) $MEM / $CPU vCPU..."

        gcloud run deploy "$TIER_SVC" \
            --image "$OLLAMA_IMAGE" \
            --region "$REGION" --project "$PROJECT_ID" \
            --service-account "$SA_EMAIL" \
            --memory "$MEM" --cpu "$CPU" \
            --no-allow-unauthenticated \
            --min-instances 0 --max-instances 3 \
            --timeout 900 --cpu-boost \
            --add-volume "name=ollama-models,type=cloud-storage,bucket=${MODELS_BUCKET}" \
            --add-volume-mount "volume=ollama-models,mount-path=/root/.ollama/models" \
            --update-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,MODEL_TIER=$TIER,OLLAMA_HOST=0.0.0.0:8080"

        TIER_URL=$(gcloud run services describe "$TIER_SVC" \
            --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
        TIER_URLS+=("$TIER=$TIER_URL")
        print_success "Tier $TIER deployed: $TIER_URL"

        gcloud run services add-iam-policy-binding "$TIER_SVC" \
            --region "$REGION" --project "$PROJECT_ID" \
            --member="serviceAccount:$SA_EMAIL" --role="roles/run.invoker" --quiet
    done

    print_header "AI Chat Model Servers (Ollama) Deployed"
    echo "Project:  $PROJECT_ID"
    echo "Region:   $REGION"
    echo "Bucket:   gs://$MODELS_BUCKET"
    for entry in "${TIER_URLS[@]}"; do echo "  $entry"; done
    echo ""
    print_info "Writing tier machines to AI config bucket..."
    write_tier_machines_to_ai_config
    echo ""
    print_warning "Re-run deploy-api with OLLAMA_TIER=true:"
    echo "  OLLAMA_TIER=true ./scripts/manual-deploy.sh deploy-api -p $PROJECT_ID -e $ENVIRONMENT"
}

deploy_model_servers() {
    deploy_model_servers_ollama
}

# =============================================================================
# Deploy Webhook-pipeline Model Server (Cloud Run B — single service, Ollama)
# =============================================================================

deploy_model_server_ollama() {
    print_header "Deploying Model Server (Ollama) to Cloud Run: $ENVIRONMENT"

    MODEL_SERVER_NAME="mem-dog-model-server-${ENVIRONMENT}"
    WEBHOOK_SA_EMAIL="mem-dog-webhook-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    OLLAMA_IMAGE="ollama/ollama:latest"
    MODELS_BUCKET="${PROJECT_ID}-mem-dog-models-${ENVIRONMENT}"

    if ! gcloud iam service-accounts describe "$WEBHOOK_SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        print_error "Webhook service account not found. Run setup-webhook first."
        exit 1
    fi

    gcloud services enable run.googleapis.com artifactregistry.googleapis.com --project="$PROJECT_ID"

    if gcloud storage buckets describe "gs://$MODELS_BUCKET" --project="$PROJECT_ID" &>/dev/null; then
        gcloud storage buckets add-iam-policy-binding "gs://$MODELS_BUCKET" \
            --member="serviceAccount:$WEBHOOK_SA_EMAIL" --role="roles/storage.objectViewer" --quiet
    else
        print_warning "Models bucket $MODELS_BUCKET not found. Run deploy-model-servers first."
        exit 1
    fi

    print_info "Deploying Ollama model server to Cloud Run..."
    gcloud run deploy "$MODEL_SERVER_NAME" \
        --image "$OLLAMA_IMAGE" \
        --region "$REGION" --project "$PROJECT_ID" \
        --service-account "$WEBHOOK_SA_EMAIL" \
        --memory 8Gi --cpu 4 \
        --no-allow-unauthenticated \
        --min-instances 0 --max-instances 3 \
        --timeout 900 --cpu-boost \
        --add-volume "name=ollama-models,type=cloud-storage,bucket=${MODELS_BUCKET}" \
        --add-volume-mount "volume=ollama-models,mount-path=/root/.ollama/models" \
        --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,OLLAMA_HOST=0.0.0.0:8080"

    MODEL_SERVER_URL=$(gcloud run services describe "$MODEL_SERVER_NAME" \
        --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')

    gcloud run services add-iam-policy-binding "$MODEL_SERVER_NAME" \
        --region "$REGION" --project "$PROJECT_ID" \
        --member="serviceAccount:$WEBHOOK_SA_EMAIL" --role="roles/run.invoker" --quiet

    print_header "Model Server (Ollama) Deployed"
    echo "URL: $MODEL_SERVER_URL"
    echo "Set MODEL_SERVER_URL when deploying the ADK agent:"
    echo "  MODEL_SERVER_URL=$MODEL_SERVER_URL OLLAMA_TIER=true $0 deploy-agent -p $PROJECT_ID -e $ENVIRONMENT"
}

deploy_model_server() {
    deploy_model_server_ollama
}

# =============================================================================
# Deploy ADK Agent to Cloud Run (Cloud Run A)
# =============================================================================

deploy_agent() {
    print_header "Deploying ADK Agent to Cloud Run: $ENVIRONMENT"

    SERVICE_NAME="mem-dog-webhook-agent-${ENVIRONMENT}"
    WEBHOOK_SA_EMAIL="mem-dog-webhook-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/webhook-agent:${ENVIRONMENT}-latest"

    # Verify service account exists (created by setup-webhook)
    if ! gcloud iam service-accounts describe "$WEBHOOK_SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        print_error "Webhook service account not found. Run setup-webhook first."
        exit 1
    fi

    # MODEL_SERVER_URL optional: agents use Gemini by default; set when using open models
    if [ -z "${MODEL_SERVER_URL:-}" ]; then
        MODEL_SERVER_URL=$(gcloud run services describe "mem-dog-model-server-${ENVIRONMENT}" \
            --region "$REGION" --project "$PROJECT_ID" \
            --format 'value(status.url)' 2>/dev/null || echo "")
    fi
    if [ -n "${MODEL_SERVER_URL:-}" ]; then
        print_success "Model server URL: $MODEL_SERVER_URL (open models enabled)"
    else
        print_info "No model server URL — agent will use Gemini only (default)"
    fi

    # Optional: deploy with Gemini API key (Google AI Studio) via Secret Manager.
    # Create secret: echo -n "YOUR_KEY" | gcloud secrets create webhook-gemini-api-key-${ENVIRONMENT} --data-file=-
    # Then: WEBHOOK_GEMINI_KEY_SECRET=webhook-gemini-api-key-${ENVIRONMENT} $0 deploy-agent ...
    GEMINI_KEY_SECRET_NAME="${WEBHOOK_GEMINI_KEY_SECRET:-webhook-gemini-api-key-${ENVIRONMENT}}"
    # Optional: Ollama Cloud fallback API key via Secret Manager (data pipeline fallback).
    # Create secret: echo -n "YOUR_OLLAMA_CLOUD_KEY" | gcloud secrets create webhook-ollama-cloud-key-${ENVIRONMENT} --data-file=-
    # Then: WEBHOOK_OLLAMA_CLOUD_KEY_SECRET=webhook-ollama-cloud-key-${ENVIRONMENT} $0 deploy-agent ...
    GEMINI_SECRET_FLAGS=""
    if [ -z "${MODEL_SERVER_URL:-}" ] && gcloud secrets describe "$GEMINI_KEY_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        gcloud secrets add-iam-policy-binding "$GEMINI_KEY_SECRET_NAME" \
            --project="$PROJECT_ID" \
            --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" --quiet 2>/dev/null || true
        GEMINI_SECRET_FLAGS="--set-secrets=GOOGLE_API_KEY=${GEMINI_KEY_SECRET_NAME}:latest"
        print_success "Gemini API key secret found — wiring GOOGLE_API_KEY (gemini/ provider)"
    fi

    # Get mem-dog API URL
    if [ -n "${MEM_DOG_API_URL:-}" ]; then
        API_URL="$MEM_DOG_API_URL"
        print_success "Using MEM_DOG_API_URL from environment: $API_URL"
    else
        print_info "Getting mem-dog API URL from Cloud Run..."
        API_URL=$(gcloud run services describe "mem-dog-api" \
            --region "$REGION" --project "$PROJECT_ID" \
            --format 'value(status.url)' 2>/dev/null || echo "")
        if [ -z "$API_URL" ]; then
            print_error "Mem-dog API not deployed to Cloud Run."
            echo ""
            echo "Either deploy the API first:"
            echo "  $0 deploy-api -p $PROJECT_ID -e $ENVIRONMENT"
            echo ""
            echo "Or provide the URL manually:"
            echo "  MEM_DOG_API_URL=https://your-api-url $0 deploy-agent -p $PROJECT_ID -e $ENVIRONMENT"
            exit 1
        fi
        print_success "Mem-dog API: $API_URL"
    fi

    WEBHOOK_STAGING_BUCKET_NAME="${PROJECT_ID}-mem-dog-webhook-staging-${ENVIRONMENT}"

    # Resolve webhook pipeline (gateway) URL so the agent can reference it if needed.
    # Prefer MEM_DOG_WEBHOOK_GATEWAY_URL; otherwise use the gateway defaultHostname if deploy-webhook was run.
    GATEWAY_NAME="mem-dog-webhook-gw-${ENVIRONMENT}"
    if [ -n "${MEM_DOG_WEBHOOK_GATEWAY_URL:-}" ]; then
        WEBHOOK_GATEWAY_URL="$MEM_DOG_WEBHOOK_GATEWAY_URL"
        print_success "Using MEM_DOG_WEBHOOK_GATEWAY_URL for agent: $WEBHOOK_GATEWAY_URL"
    else
        GATEWAY_HOST=$(gcloud api-gateway gateways describe "$GATEWAY_NAME" \
            --location="$REGION" --project="$PROJECT_ID" \
            --format='value(defaultHostname)' 2>/dev/null || echo "")
        if [ -n "$GATEWAY_HOST" ]; then
            WEBHOOK_GATEWAY_URL="https://${GATEWAY_HOST}/webhook"
            print_success "Webhook pipeline URL (for agent): $WEBHOOK_GATEWAY_URL"
        else
            WEBHOOK_GATEWAY_URL=""
            print_info "Webhook gateway not found — run deploy-webhook first to set WEBHOOK_GATEWAY_URL on the agent"
        fi
    fi

    # Enable required APIs
    print_info "Enabling required APIs..."
    gcloud services enable \
        run.googleapis.com \
        artifactregistry.googleapis.com \
        --project="$PROJECT_ID"
    print_success "APIs enabled"

    # Build image (linux/amd64 for Cloud Run)
    print_info "Building ADK agent Docker image for linux/amd64..."
    cd "$ROOT_DIR"
    docker buildx build \
        --no-cache \
        --platform linux/amd64 \
        -t "$IMAGE_TAG" \
        --load \
        -f webhook/processor/Dockerfile \
        webhook/processor
    print_success "Image built"

    # Push to Artifact Registry
    print_info "Pushing image to Artifact Registry..."
    docker push "$IMAGE_TAG"
    print_success "Image pushed"

    # Data processing pipeline AI: Ollama Cloud primary (per-tier), Gemini fallback.
    # Override via env: DATA_PIPELINE_AI_PRIMARY_MODEL, DATA_PIPELINE_AI_FALLBACK_MODEL, etc.
    DATA_PIPELINE_PRIMARY="${DATA_PIPELINE_AI_PRIMARY_MODEL:-}"
    DATA_PIPELINE_FALLBACK="${DATA_PIPELINE_AI_FALLBACK_MODEL:-${FALLBACK_LITELLM_MODEL}}"
    DATA_PIPELINE_FALLBACK_ENABLED="${DATA_PIPELINE_AI_FALLBACK_ENABLED:-true}"
    AGENT_PREFER_GEMINI="${AGENT_PREFER_GEMINI:-false}"
    if [ -z "$DATA_PIPELINE_PRIMARY" ]; then
        if [ -n "${MODEL_SERVER_URL:-}" ]; then
            DATA_PIPELINE_PRIMARY="gemini/${GEMINI_MODEL}"
        elif [ -n "$GEMINI_SECRET_FLAGS" ]; then
            DATA_PIPELINE_PRIMARY="gemini/${GEMINI_MODEL}"
        else
            DATA_PIPELINE_PRIMARY="vertex_ai/${GEMINI_MODEL}"
        fi
    fi
    # Per-tier Ollama Cloud models (primary provider when AGENT_PREFER_GEMINI=false).
    OC_MODEL_SMALL="${OLLAMA_CLOUD_MODEL_SMALL:-ollama/gemma3:4b}"
    OC_MODEL_MEDIUM="${OLLAMA_CLOUD_MODEL_MEDIUM:-ollama/gemma3:12b}"
    OC_MODEL_LARGE="${OLLAMA_CLOUD_MODEL_LARGE:-ollama/gemma3:27b}"
    OC_MODEL_MULTIMODAL="${OLLAMA_CLOUD_MODEL_MULTIMODAL:-ollama/qwen3-vl:235b-cloud}"
    OC_MODEL_OMNI="${OLLAMA_CLOUD_MODEL_OMNI:-ollama/qwen3.5:cloud}"
    PIPELINE_ENV="DATA_PIPELINE_AI_PRIMARY_MODEL=$DATA_PIPELINE_PRIMARY,DATA_PIPELINE_AI_FALLBACK_MODEL=$DATA_PIPELINE_FALLBACK,DATA_PIPELINE_AI_FALLBACK_ENABLED=$DATA_PIPELINE_FALLBACK_ENABLED,AGENT_PREFER_GEMINI=$AGENT_PREFER_GEMINI,OLLAMA_CLOUD_MODEL_SMALL=$OC_MODEL_SMALL,OLLAMA_CLOUD_MODEL_MEDIUM=$OC_MODEL_MEDIUM,OLLAMA_CLOUD_MODEL_LARGE=$OC_MODEL_LARGE,OLLAMA_CLOUD_MODEL_MULTIMODAL=$OC_MODEL_MULTIMODAL,OLLAMA_CLOUD_MODEL_OMNI=$OC_MODEL_OMNI"
    [ -n "${WEBHOOK_GATEWAY_URL:-}" ] && PIPELINE_ENV="$PIPELINE_ENV,WEBHOOK_GATEWAY_URL=$WEBHOOK_GATEWAY_URL"

    # Optional: Ollama Cloud API key from Secret Manager (required for Ollama Cloud primary).
    OLLAMA_CLOUD_SECRET_FLAGS=""
    OLLAMA_CLOUD_SECRET_NAME="${WEBHOOK_OLLAMA_CLOUD_KEY_SECRET:-}"
    if [ -n "$OLLAMA_CLOUD_SECRET_NAME" ] && gcloud secrets describe "$OLLAMA_CLOUD_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        gcloud secrets add-iam-policy-binding "$OLLAMA_CLOUD_SECRET_NAME" \
            --project="$PROJECT_ID" \
            --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" --quiet 2>/dev/null || true
        OLLAMA_CLOUD_SECRET_FLAGS="--set-secrets=OLLAMA_CLOUD_API_KEY=${OLLAMA_CLOUD_SECRET_NAME}:latest"
        print_success "Ollama Cloud API key secret found — wiring OLLAMA_CLOUD_API_KEY"
    fi

    # Deploy to Cloud Run.
    # --no-allow-unauthenticated: only the webhook Cloud Function can invoke it.
    # When using Gemini: GOOGLE_API_KEY from Secret Manager (gemini/ provider) or Vertex (vertex_ai/).
    print_info "Deploying ADK agent to Cloud Run..."
    if [ -n "${MODEL_SERVER_URL:-}" ]; then
        EXTRA_ENV="GOOGLE_GENAI_USE_VERTEXAI=FALSE,MODEL_SERVER_URL=$MODEL_SERVER_URL,MODEL_SERVER_MODEL=gemma,ADK_MODEL=openai/gemma"
    elif [ -n "$GEMINI_SECRET_FLAGS" ]; then
        EXTRA_ENV="ADK_MODEL=gemini/${GEMINI_MODEL},GEMINI_MODEL=gemini/${GEMINI_MODEL}"
    else
        EXTRA_ENV="GOOGLE_GENAI_USE_VERTEXAI=TRUE,ADK_MODEL=vertex_ai/${GEMINI_MODEL},GEMINI_MODEL=vertex_ai/${GEMINI_MODEL}"
    fi
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --service-account "$WEBHOOK_SA_EMAIL" \
        --memory 1Gi \
        --cpu 1 \
        --no-allow-unauthenticated \
        --min-instances 0 \
        --max-instances 5 \
        --timeout 600 \
        $GEMINI_SECRET_FLAGS \
        $OLLAMA_CLOUD_SECRET_FLAGS \
        --set-env-vars "\
MEM_DOG_API_URL=$API_URL,\
WEBHOOK_STAGING_BUCKET=$WEBHOOK_STAGING_BUCKET_NAME,\
DEFAULT_USER=${DEFAULT_USER:-demo},\
SYSTEM_USER_ID=${SYSTEM_USER_ID:-${DEFAULT_USER:-demo}},\
$PIPELINE_ENV,\
$EXTRA_ENV"
    print_success "Cloud Run service deployed"

    # Retrieve the service URL
    AGENT_SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region "$REGION" --project "$PROJECT_ID" \
        --format 'value(status.url)')
    print_success "Agent service URL: $AGENT_SERVICE_URL"

    # Grant the webhook SA permission to invoke this Cloud Run service
    gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
        --region "$REGION" --project "$PROJECT_ID" \
        --member="serviceAccount:$WEBHOOK_SA_EMAIL" \
        --role="roles/run.invoker" --quiet
    print_success "Granted run.invoker to webhook SA on agent service"

    # Propagate the service URL to the processor Cloud Function (if deployed).
    # Cloud Functions 2nd gen run on Cloud Run, so update the env var directly
    # on the underlying Cloud Run service — no need to redeploy from source.
    PROCESSOR_NAME="mem-dog-webhook-processor-${ENVIRONMENT}"
    if gcloud functions describe "$PROCESSOR_NAME" \
        --gen2 --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        print_info "Updating processor function with AGENT_SERVICE_URL..."
        gcloud run services update "$PROCESSOR_NAME" \
            --region="$REGION" --project="$PROJECT_ID" \
            --update-env-vars "AGENT_SERVICE_URL=$AGENT_SERVICE_URL"
        print_success "Processor function updated"
    else
        print_warning "Processor function not yet deployed — run deploy-webhook after this step and AGENT_SERVICE_URL will be picked up automatically."
    fi

    print_header "ADK Agent Deployed to Cloud Run"
    echo "Project:           $PROJECT_ID"
    echo "Region:            $REGION"
    echo "Service:           $SERVICE_NAME"
    echo "URL:               $AGENT_SERVICE_URL"
    echo "API URL:           $API_URL"
    [ -n "${WEBHOOK_GATEWAY_URL:-}" ] && echo "Webhook pipeline:   $WEBHOOK_GATEWAY_URL"
    echo "Model Server URL:  ${MODEL_SERVER_URL:-(none — using Gemini)}"
    echo "Data pipeline AI:  primary=$DATA_PIPELINE_PRIMARY  fallback=$DATA_PIPELINE_FALLBACK (enabled=$DATA_PIPELINE_FALLBACK_ENABLED)  prefer_gemini=$AGENT_PREFER_GEMINI"
    echo "Ollama Cloud tiers: small=$OC_MODEL_SMALL  medium=$OC_MODEL_MEDIUM  large=$OC_MODEL_LARGE  multimodal=$OC_MODEL_MULTIMODAL"
    [ -n "$GEMINI_SECRET_FLAGS" ] && echo "Gemini API key:     from Secret Manager ($GEMINI_KEY_SECRET_NAME)"
    [ -n "$OLLAMA_CLOUD_SECRET_FLAGS" ] && echo "Ollama Cloud key:   from Secret Manager ($OLLAMA_CLOUD_SECRET_NAME)"
    echo ""
    echo "The processor Cloud Function calls POST \$AGENT_SERVICE_URL/run"
    echo "to invoke the agent for each webhook payload."
}

# =============================================================================
# Deploy Webhook Pipeline
# =============================================================================

deploy_webhook() {
    print_header "Deploying Webhook Pipeline: $ENVIRONMENT"

    TOPIC_NAME="mem-dog-webhook-${ENVIRONMENT}"
    WEBHOOK_SA_EMAIL="mem-dog-webhook-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    RECEIVER_NAME="mem-dog-webhook-receiver-${ENVIRONMENT}"
    PROCESSOR_NAME="mem-dog-webhook-processor-${ENVIRONMENT}"
    GATEWAY_NAME="mem-dog-webhook-gw-${ENVIRONMENT}"
    API_CONFIG_NAME="mem-dog-webhook-api-${ENVIRONMENT}"

    # Verify service account exists
    if ! gcloud iam service-accounts describe "$WEBHOOK_SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        print_error "Webhook service account not found. Run setup-webhook first."
        exit 1
    fi

    # Verify Pub/Sub topic exists
    if ! gcloud pubsub topics describe "$TOPIC_NAME" --project="$PROJECT_ID" &>/dev/null; then
        print_error "Pub/Sub topic not found. Run setup-webhook first."
        exit 1
    fi

    # Get mem-dog API URL (supports MEM_DOG_API_URL env var override)
    if [ -n "$MEM_DOG_API_URL" ]; then
        API_URL="$MEM_DOG_API_URL"
        print_success "Using MEM_DOG_API_URL from environment: $API_URL"
    else
        print_info "Getting mem-dog API URL from Cloud Run..."
        API_URL=$(gcloud run services describe "mem-dog-api" \
            --region "$REGION" --project "$PROJECT_ID" \
            --format 'value(status.url)' 2>/dev/null || echo "")
        if [ -z "$API_URL" ]; then
            print_error "Mem-dog API not deployed to Cloud Run."
            echo ""
            echo "Either deploy the API first:"
            echo "  $0 deploy-api -p $PROJECT_ID -e $ENVIRONMENT"
            echo ""
            echo "Or provide the URL manually:"
            echo "  MEM_DOG_API_URL=https://your-api-url $0 deploy-webhook -p $PROJECT_ID -e $ENVIRONMENT"
            exit 1
        fi
        print_success "Mem-dog API: $API_URL"
    fi

    # Deploy receiver Cloud Function
    # No --allow-unauthenticated: the API Gateway authenticates via its
    # backend service account configured in the OpenAPI spec.
    print_info "Deploying receiver Cloud Function..."
    cd "$ROOT_DIR"
    gcloud functions deploy "$RECEIVER_NAME" \
        --gen2 \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --runtime=python311 \
        --source=webhook/receiver \
        --entry-point=webhook_receiver \
        --trigger-http \
        --no-allow-unauthenticated \
        --service-account="$WEBHOOK_SA_EMAIL" \
        --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,WEBHOOK_PUBSUB_TOPIC=$TOPIC_NAME,MEM_DOG_API_URL=$API_URL" \
        --memory=256Mi \
        --timeout=30s \
        --min-instances=0 \
        --max-instances=10
    print_success "Receiver function deployed"

    # Get receiver function URL
    RECEIVER_URL=$(gcloud functions describe "$RECEIVER_NAME" \
        --gen2 --region="$REGION" --project="$PROJECT_ID" \
        --format='value(serviceConfig.uri)')
    print_success "Receiver URL: $RECEIVER_URL"

    # Resolve AGENT_SERVICE_URL — required by the processor to call Cloud Run A.
    # Accept an explicit override from the shell environment, then fall back to
    # auto-detecting the URL of the already-deployed agent Cloud Run service.
    AGENT_SVC_NAME="mem-dog-webhook-agent-${ENVIRONMENT}"
    if [ -z "${AGENT_SERVICE_URL:-}" ]; then
        AGENT_SERVICE_URL=$(gcloud run services describe "$AGENT_SVC_NAME" \
            --region "$REGION" --project "$PROJECT_ID" \
            --format 'value(status.url)' 2>/dev/null || echo "")
    fi
    _PROC_USER="${DEFAULT_USER:-demo}"
    _PROC_SYSUSER="${SYSTEM_USER_ID:-$_PROC_USER}"
    if [ -z "${AGENT_SERVICE_URL:-}" ]; then
        print_warning "Agent service not yet deployed — processor will start without AGENT_SERVICE_URL."
        print_warning "Run deploy-agent after deploy-webhook to complete the wiring."
        PROCESSOR_ENV_VARS="GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=$REGION,MEM_DOG_API_URL=$API_URL,AGENT_RUN_TIMEOUT_S=480,DEFAULT_USER=$_PROC_USER,SYSTEM_USER_ID=$_PROC_SYSUSER"
    else
        print_success "Agent service URL: $AGENT_SERVICE_URL"
        PROCESSOR_ENV_VARS="GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=$REGION,AGENT_SERVICE_URL=$AGENT_SERVICE_URL,MEM_DOG_API_URL=$API_URL,AGENT_RUN_TIMEOUT_S=480,DEFAULT_USER=$_PROC_USER,SYSTEM_USER_ID=$_PROC_SYSUSER"
    fi

    # Deploy processor Cloud Function
    print_info "Deploying processor Cloud Function..."
    gcloud functions deploy "$PROCESSOR_NAME" \
        --gen2 \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --runtime=python311 \
        --source=webhook/processor \
        --entry-point=webhook_processor \
        --trigger-topic="$TOPIC_NAME" \
        --service-account="$WEBHOOK_SA_EMAIL" \
        --set-env-vars="$PROCESSOR_ENV_VARS" \
        --memory=1Gi \
        --timeout=540s \
        --min-instances=0 \
        --max-instances=5
    print_success "Processor function deployed"

    # Prepare and deploy API Gateway
    print_info "Deploying API Gateway..."

    TEMP_SPEC=$(mktemp /tmp/openapi-spec-XXXXXX.yaml)
    sed "s|RECEIVER_FUNCTION_URL|$RECEIVER_URL|g" "$ROOT_DIR/webhook/openapi-spec.yaml" > "$TEMP_SPEC"
    sed -i.bak "s|GATEWAY_HOST|${GATEWAY_NAME}.apigateway.${PROJECT_ID}.cloud.goog|g" "$TEMP_SPEC"
    rm -f "${TEMP_SPEC}.bak"

    # Create API (idempotent)
    gcloud api-gateway apis create "$API_CONFIG_NAME" \
        --project="$PROJECT_ID" 2>/dev/null || true

    # Create API config
    CONFIG_VERSION="${API_CONFIG_NAME}-v$(date +%Y%m%d%H%M%S)"
    gcloud api-gateway api-configs create "$CONFIG_VERSION" \
        --api="$API_CONFIG_NAME" \
        --openapi-spec="$TEMP_SPEC" \
        --project="$PROJECT_ID" \
        --backend-auth-service-account="$WEBHOOK_SA_EMAIL"
    print_success "API config created: $CONFIG_VERSION"

    # Create or update gateway
    if gcloud api-gateway gateways describe "$GATEWAY_NAME" \
        --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        gcloud api-gateway gateways update "$GATEWAY_NAME" \
            --api="$API_CONFIG_NAME" \
            --api-config="$CONFIG_VERSION" \
            --location="$REGION" \
            --project="$PROJECT_ID"
        print_success "API Gateway updated"
    else
        gcloud api-gateway gateways create "$GATEWAY_NAME" \
            --api="$API_CONFIG_NAME" \
            --api-config="$CONFIG_VERSION" \
            --location="$REGION" \
            --project="$PROJECT_ID"
        print_success "API Gateway created"
    fi

    rm -f "$TEMP_SPEC"

    # Get gateway URL
    GATEWAY_URL=$(gcloud api-gateway gateways describe "$GATEWAY_NAME" \
        --location="$REGION" --project="$PROJECT_ID" \
        --format='value(defaultHostname)')

    # Enable the managed service created by API Gateway
    MANAGED_SERVICE=$(gcloud api-gateway apis describe "$API_CONFIG_NAME" \
        --project="$PROJECT_ID" \
        --format='value(managedService)')
    if [[ -n "$MANAGED_SERVICE" ]]; then
        print_info "Enabling API Gateway managed service: $MANAGED_SERVICE"
        gcloud services enable "$MANAGED_SERVICE" --project="$PROJECT_ID"
        print_success "Managed service enabled"
    fi

    print_header "Webhook Pipeline Deployed"
    echo "Environment:       $ENVIRONMENT"
    echo "Gateway URL:       https://$GATEWAY_URL"
    echo "Receiver Function: $RECEIVER_NAME"
    echo "Processor Function:$PROCESSOR_NAME"
    echo "Pub/Sub Topic:     $TOPIC_NAME"
    echo "Mem-Dog API:       $API_URL"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Deploy the ADK agent to Cloud Run:"
    echo "   $0 deploy-agent -p $PROJECT_ID -e $ENVIRONMENT"
    echo "   (This also sets AGENT_SERVICE_URL on the processor function automatically.)"
    echo ""
    echo "2. Create an API key in the GCP Console:"
    echo "   APIs & Services > Credentials > Create Credentials > API Key"
    echo ""
    echo "4. Test with:"
    echo "   curl -X POST https://$GATEWAY_URL/webhook \\"
    echo "     -H 'x-api-key: YOUR_API_KEY' \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"event\": \"test\", \"data\": {\"hello\": \"world\"}}'"
}

# =============================================================================
# URL Dependencies (environment variables used by deploy commands)
# =============================================================================

print_url_dependencies() {
    print_header "URL Dependencies (Environment Variables)"
    echo "Resolved URLs and bucket names (as used by deploy-api / deploy-ui):"
    echo "  (API/UI URLs: use MEM_DOG_API_URL to override if gcloud returns a different URL than your canonical one.)"
    echo ""

    # API URL: prefer MEM_DOG_API_URL override, then project-number URL, then gcloud status.url
    API_URL=""
    if [ -n "${MEM_DOG_API_URL:-}" ]; then
        API_URL="$MEM_DOG_API_URL"
        echo "  API_URL (mem-dog-api)              = $API_URL  [from MEM_DOG_API_URL]"
    else
        PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format 'value(projectNumber)' 2>/dev/null || echo "")
        if [ -n "$PROJECT_NUMBER" ]; then
            # Canonical Cloud Run URL (project-number based); often more stable than hash-based status.url
            API_URL="https://mem-dog-api-${PROJECT_NUMBER}.${REGION}.run.app"
            echo "  API_URL (mem-dog-api)              = $API_URL  [project-number URL]"
        else
            API_URL=$(gcloud run services describe "mem-dog-api" --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)' 2>/dev/null || echo "")
            if [ -n "$API_URL" ]; then
                echo "  API_URL (mem-dog-api)              = $API_URL  [from gcloud status.url]"
            else
                echo "  API_URL (mem-dog-api)              = (not deployed)"
            fi
        fi
    fi

    # UI (NEXT_PUBLIC_API_URL is what the UI uses to call the API)
    UI_SVC="mem-dog-ui-${ENVIRONMENT}"
    if [ -n "$API_URL" ]; then
        echo "  NEXT_PUBLIC_API_URL (UI → API)     = $API_URL"
    else
        echo "  NEXT_PUBLIC_API_URL (UI → API)     = (set after API is deployed)"
    fi
    UI_URL=$(gcloud run services describe "$UI_SVC" --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)' 2>/dev/null || echo "")
    if [ -n "$UI_URL" ]; then
        echo "  UI_URL ($UI_SVC)                   = $UI_URL"
    else
        echo "  UI_URL ($UI_SVC)                   = (not deployed)"
    fi

    # Download Function (API uses Pub/Sub topic when set)
    DOWNLOAD_TOPIC="mem-dog-downloads-${ENVIRONMENT}"
    if gcloud pubsub topics describe "$DOWNLOAD_TOPIC" --project="$PROJECT_ID" &>/dev/null; then
        echo "  DOWNLOAD_TOPIC                     = $DOWNLOAD_TOPIC"
    fi

    # Model tiers (AI Chat)
    for TIER in small medium large very-large; do
        TIER_SVC="mem-dog-model-server-${TIER}-${ENVIRONMENT}"
        T_URL=$(gcloud run services describe "$TIER_SVC" --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)' 2>/dev/null || echo "")
        if [ -n "$T_URL" ]; then
            TIER_UPPER=$(echo "$TIER" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
            echo "  MODEL_SERVER_URL_${TIER_UPPER} ($TIER_SVC) = $T_URL"
        fi
    done

    # System config
    SYSCONFIG_BUCKET="${PROJECT_ID}-mem-dog-sysconfig-${ENVIRONMENT}"
    echo "  SYSTEM_CONFIG_BUCKET               = $SYSCONFIG_BUCKET"

    # Current API service env vars (if deployed and jq available)
    if command -v jq &>/dev/null && gcloud run services describe "mem-dog-api" --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
        echo ""
        echo "Current API service environment variables (mem-dog-api):"
        gcloud run services describe "mem-dog-api" --region "$REGION" --project "$PROJECT_ID" --format=json 2>/dev/null | \
            jq -r '.spec.template.spec.containers[0].env[]? |
                if .value != null then
                    "  \(.name)=\(.value)"
                elif .valueFrom.secretKeyRef != null then
                    "  \(.name)=[secret: \(.valueFrom.secretKeyRef.name)]"
                else
                    "  \(.name)=(unset)"
                end' 2>/dev/null || echo "  (unable to list)"
    fi
    echo ""
}

# =============================================================================
# Deploy Webhook Gateway to Cloud Run
# =============================================================================

deploy_webhook_gateway() {
    print_header "Deploying Webhook Gateway to Cloud Run: $ENVIRONMENT"

    SERVICE_NAME="mem-dog-webhook-gateway-${ENVIRONMENT}"
    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/webhook-gateway:${ENVIRONMENT}-latest"
    SA_EMAIL="mem-dog-cloud-run-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"

    # Verify service account exists (created by setup-env)
    if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        print_error "Cloud Run service account not found. Run setup-env first."
        exit 1
    fi

    # ── Resolve mem-dog API URL ────────────────────────────────────────────
    if [ -n "${MEM_DOG_API_URL:-}" ]; then
        WGW_API_URL="$MEM_DOG_API_URL"
        print_success "Using MEM_DOG_API_URL from environment: $WGW_API_URL"
    else
        print_info "Getting mem-dog API URL from Cloud Run..."
        WGW_API_URL=$(gcloud run services describe "mem-dog-api" \
            --region "$REGION" --project "$PROJECT_ID" \
            --format 'value(status.url)' 2>/dev/null || echo "")
        if [ -z "$WGW_API_URL" ]; then
            print_error "Mem-dog API not deployed to Cloud Run."
            echo ""
            echo "Either deploy the API first:"
            echo "  $0 deploy-api -p $PROJECT_ID -e $ENVIRONMENT"
            echo ""
            echo "Or provide the URL manually:"
            echo "  MEM_DOG_API_URL=https://your-api-url $0 deploy-webhook-gateway -p $PROJECT_ID -e $ENVIRONMENT"
            exit 1
        fi
        print_success "Mem-dog API: $WGW_API_URL"
    fi

    # ── Resolve webhook gateway URL ────────────────────────────────────────
    if [ -n "${MEM_DOG_WEBHOOK_GATEWAY_URL:-}" ]; then
        WGW_WEBHOOK_URL="$MEM_DOG_WEBHOOK_GATEWAY_URL"
        print_success "Using MEM_DOG_WEBHOOK_GATEWAY_URL from environment: $WGW_WEBHOOK_URL"
    else
        GATEWAY_NAME="mem-dog-webhook-gw-${ENVIRONMENT}"
        GATEWAY_HOST=$(gcloud api-gateway gateways describe "$GATEWAY_NAME" \
            --location="$REGION" --project="$PROJECT_ID" \
            --format='value(defaultHostname)' 2>/dev/null || echo "")
        if [ -n "$GATEWAY_HOST" ]; then
            WGW_WEBHOOK_URL="https://${GATEWAY_HOST}/webhook"
            print_success "Webhook gateway URL: $WGW_WEBHOOK_URL"
        else
            WGW_WEBHOOK_URL=""
            print_warning "Webhook gateway not found — run deploy-webhook first, or set MEM_DOG_WEBHOOK_GATEWAY_URL"
        fi
    fi

    # ── Resolve webhook API key ────────────────────────────────────────────
    WGW_WEBHOOK_KEY="${MEM_DOG_WEBHOOK_API_KEY:-}"
    WEBHOOK_KEY_SECRET_NAME="mem-dog-webhook-api-key-${ENVIRONMENT}"
    WEBHOOK_KEY_SECRET_FLAGS=""
    if [ -z "$WGW_WEBHOOK_KEY" ] && gcloud secrets describe "$WEBHOOK_KEY_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        gcloud secrets add-iam-policy-binding "$WEBHOOK_KEY_SECRET_NAME" \
            --project="$PROJECT_ID" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" --quiet 2>/dev/null || true
        WEBHOOK_KEY_SECRET_FLAGS="--set-secrets=WEBHOOK_API_KEY=${WEBHOOK_KEY_SECRET_NAME}:latest"
        print_success "Webhook API key from Secret Manager ($WEBHOOK_KEY_SECRET_NAME)"
    elif [ -n "$WGW_WEBHOOK_KEY" ]; then
        print_success "Using MEM_DOG_WEBHOOK_API_KEY from environment"
    fi

    # ── Resolve LLM provider secrets ───────────────────────────────────────
    WGW_LLM_PROVIDER="${LLM_PROVIDER:-gemini}"
    LLM_SECRET_FLAGS=""

    # Gemini API key
    GEMINI_KEY_SECRET_NAME="${WGW_GEMINI_KEY_SECRET:-wgw-gemini-api-key-${ENVIRONMENT}}"
    if [ "$WGW_LLM_PROVIDER" = "gemini" ] || [ -z "${LLM_API_KEY:-}" ]; then
        if gcloud secrets describe "$GEMINI_KEY_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
            gcloud secrets add-iam-policy-binding "$GEMINI_KEY_SECRET_NAME" \
                --project="$PROJECT_ID" \
                --member="serviceAccount:$SA_EMAIL" \
                --role="roles/secretmanager.secretAccessor" --quiet 2>/dev/null || true
            LLM_SECRET_FLAGS="--set-secrets=GEMINI_API_KEY=${GEMINI_KEY_SECRET_NAME}:latest"
            print_success "Gemini API key from Secret Manager ($GEMINI_KEY_SECRET_NAME)"
        elif [ -n "${GEMINI_API_KEY:-}" ]; then
            print_success "Using GEMINI_API_KEY from environment"
        else
            print_warning "No Gemini API key found — create secret or set GEMINI_API_KEY env var"
            echo "  echo -n 'YOUR_KEY' | gcloud secrets create $GEMINI_KEY_SECRET_NAME --data-file=- --project=$PROJECT_ID"
        fi
    fi

    # Generic LLM_API_KEY (for non-Gemini providers)
    LLM_KEY_SECRET_NAME="${WGW_LLM_KEY_SECRET:-wgw-llm-api-key-${ENVIRONMENT}}"
    if [ "$WGW_LLM_PROVIDER" != "gemini" ]; then
        if gcloud secrets describe "$LLM_KEY_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
            gcloud secrets add-iam-policy-binding "$LLM_KEY_SECRET_NAME" \
                --project="$PROJECT_ID" \
                --member="serviceAccount:$SA_EMAIL" \
                --role="roles/secretmanager.secretAccessor" --quiet 2>/dev/null || true
            LLM_SECRET_FLAGS="${LLM_SECRET_FLAGS:+$LLM_SECRET_FLAGS,}LLM_API_KEY=${LLM_KEY_SECRET_NAME}:latest"
            print_success "LLM API key from Secret Manager ($LLM_KEY_SECRET_NAME)"
        elif [ -n "${LLM_API_KEY:-}" ]; then
            print_success "Using LLM_API_KEY from environment for provider: $WGW_LLM_PROVIDER"
        else
            print_warning "No LLM_API_KEY found for provider $WGW_LLM_PROVIDER"
        fi
    fi

    # ── Enable required APIs ───────────────────────────────────────────────
    print_info "Enabling required APIs..."
    gcloud services enable \
        run.googleapis.com \
        artifactregistry.googleapis.com \
        --project="$PROJECT_ID"
    print_success "APIs enabled"

    # ── Build Docker image ─────────────────────────────────────────────────
    print_info "Building Webhook Gateway Docker image for linux/amd64..."
    cd "$ROOT_DIR"
    docker buildx build \
        --platform linux/amd64 \
        -t "$IMAGE_TAG" \
        --load \
        -f webhook-gateway/Dockerfile \
        webhook-gateway
    print_success "Image built"

    # ── Push to Artifact Registry ──────────────────────────────────────────
    print_info "Pushing image to Artifact Registry..."
    docker push "$IMAGE_TAG"
    print_success "Image pushed"

    # ── Build env vars string ──────────────────────────────────────────────
    ENV_VARS="LLM_PROVIDER=$WGW_LLM_PROVIDER"
    ENV_VARS="$ENV_VARS,LLM_MODEL=${LLM_MODEL:-}"
    ENV_VARS="$ENV_VARS,GEMINI_MODEL=${GEMINI_MODEL}"
    ENV_VARS="$ENV_VARS,MEM_DOG_API_URL=$WGW_API_URL"
    [ -n "$WGW_WEBHOOK_URL" ] && ENV_VARS="$ENV_VARS,WEBHOOK_GATEWAY_URL=$WGW_WEBHOOK_URL"
    [ -n "$WGW_WEBHOOK_KEY" ] && ENV_VARS="$ENV_VARS,WEBHOOK_API_KEY=$WGW_WEBHOOK_KEY"
    [ -n "${LLM_API_BASE:-}" ] && ENV_VARS="$ENV_VARS,LLM_API_BASE=$LLM_API_BASE"
    [ -n "${LLM_API_KEY:-}" ] && [ "$WGW_LLM_PROVIDER" != "gemini" ] && ENV_VARS="$ENV_VARS,LLM_API_KEY=$LLM_API_KEY"
    [ -n "${GEMINI_API_KEY:-}" ] && ENV_VARS="$ENV_VARS,GEMINI_API_KEY=$GEMINI_API_KEY"
    ENV_VARS="$ENV_VARS,OTEL_ENABLED=${OTEL_ENABLED:-true}"
    ENV_VARS="$ENV_VARS,OTEL_SERVICE_NAME=webhook-gateway"
    ENV_VARS="$ENV_VARS,LOG_LEVEL=${LOG_LEVEL:-INFO}"
    [ -n "${WGW_API_KEY:-}" ] && ENV_VARS="$ENV_VARS,WGW_API_KEY=$WGW_API_KEY"
    [ -n "${WGW_RATE_LIMIT:-}" ] && ENV_VARS="$ENV_VARS,WGW_RATE_LIMIT=$WGW_RATE_LIMIT"
    [ -n "${WGW_CORS_ORIGINS:-}" ] && ENV_VARS="$ENV_VARS,WGW_CORS_ORIGINS=$WGW_CORS_ORIGINS"

    # ── Deploy to Cloud Run ────────────────────────────────────────────────
    print_info "Deploying Webhook Gateway to Cloud Run..."
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --service-account "$SA_EMAIL" \
        --memory 512Mi \
        --cpu 1 \
        --allow-unauthenticated \
        --min-instances 0 \
        --max-instances 10 \
        --timeout 60 \
        --port 8080 \
        $LLM_SECRET_FLAGS \
        $WEBHOOK_KEY_SECRET_FLAGS \
        --set-env-vars "$ENV_VARS"
    print_success "Cloud Run service deployed"

    # ── Retrieve service URL ───────────────────────────────────────────────
    WGW_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region "$REGION" --project "$PROJECT_ID" \
        --format 'value(status.url)')
    print_success "Webhook Gateway URL: $WGW_URL"

    print_header "Webhook Gateway Deployed"
    echo "Project:            $PROJECT_ID"
    echo "Region:             $REGION"
    echo "Service:            $SERVICE_NAME"
    echo "URL:                $WGW_URL"
    echo "API URL:            $WGW_API_URL"
    echo "Webhook Gateway:    ${WGW_WEBHOOK_URL:-(not configured)}"
    echo "LLM Provider:       $WGW_LLM_PROVIDER"
    echo "LLM Model:          ${LLM_MODEL:-${GEMINI_MODEL}}"
    [ -n "$LLM_SECRET_FLAGS" ] && echo "LLM key:            from Secret Manager"
    [ -n "$WEBHOOK_KEY_SECRET_FLAGS" ] && echo "Webhook API key:    from Secret Manager"
    echo ""
    echo "Endpoints:"
    echo "  Swagger docs:  $WGW_URL/docs"
    echo "  Webhooks:      $WGW_URL/webhooks/{channel_type}"
    echo "  Health:        $WGW_URL/health"
    echo "  Providers:     $WGW_URL/providers"
    echo ""
    echo "LLM secrets (create if not already done):"
    echo "  echo -n 'YOUR_KEY' | gcloud secrets create $GEMINI_KEY_SECRET_NAME --data-file=- --project=$PROJECT_ID"
    echo "  echo -n 'YOUR_KEY' | gcloud secrets create $LLM_KEY_SECRET_NAME --data-file=- --project=$PROJECT_ID"
}

# =============================================================================
# Deploy Webhook Gateway to GKE (open-jaws Gateway)
# =============================================================================

deploy_webhook_gateway_gke() {
    print_header "Deploying Webhook Gateway to GKE: $ENVIRONMENT"

    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/webhook-gateway:${ENVIRONMENT}-latest"
    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    # ── Verify GKE cluster ─────────────────────────────────────────────────
    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            echo ""
            echo "Set GKE_CLUSTER and GKE_ZONE (or use a regional cluster):"
            echo "  GKE_CLUSTER=my-cluster GKE_ZONE=${REGION}-a $0 deploy-webhook-gateway-gke -p $PROJECT_ID -e $ENVIRONMENT"
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    # ── Verify kubectl ─────────────────────────────────────────────────────
    if ! command -v kubectl &>/dev/null; then
        print_error "kubectl not found. Install: gcloud components install kubectl"
        exit 1
    fi
    print_success "kubectl found"

    # ── Resolve mem-dog API URL ────────────────────────────────────────────
    # Priority: env var > in-cluster K8s service > Cloud Run
    if [ -z "${MEM_DOG_API_URL:-}" ]; then
        # Check if the API service exists in the same cluster
        if kubectl get service api -n mem-dog &>/dev/null; then
            MEM_DOG_API_URL="http://api.mem-dog.svc.cluster.local:8080"
            print_success "MEM_DOG_API_URL (in-cluster): $MEM_DOG_API_URL"
        else
            MEM_DOG_API_URL=$(gcloud run services describe "mem-dog-api" \
                --region "$REGION" --project "$PROJECT_ID" \
                --format 'value(status.url)' 2>/dev/null || echo "")
            if [ -z "$MEM_DOG_API_URL" ]; then
                print_error "MEM_DOG_API_URL not set and mem-dog API not found (in-cluster or Cloud Run)."
                echo "  Set MEM_DOG_API_URL explicitly or deploy the API first."
                exit 1
            fi
            print_success "MEM_DOG_API_URL (Cloud Run): $MEM_DOG_API_URL"
        fi
    else
        print_success "MEM_DOG_API_URL (override): $MEM_DOG_API_URL"
    fi

    # ── Resolve webhook gateway URL ────────────────────────────────────────
    # Must point at the webhook *receiver* (pipeline entry), not API ingest.
    # OpenClaw sends {data, telemetry}; /api/v1/ingest expects {envelope, direct} — wrong shape.
    # Priority: env var > in-cluster receiver (when present) > GCP API Gateway > fallback ingest
    if [ -n "${MEM_DOG_WEBHOOK_GATEWAY_URL:-}" ]; then
        print_success "WEBHOOK_GATEWAY_URL (override): $MEM_DOG_WEBHOOK_GATEWAY_URL"
    elif kubectl get service webhook-receiver -n webhook-pipeline &>/dev/null; then
        MEM_DOG_WEBHOOK_GATEWAY_URL="http://webhook-receiver.webhook-pipeline.svc.cluster.local:8080"
        print_success "WEBHOOK_GATEWAY_URL (in-cluster receiver): $MEM_DOG_WEBHOOK_GATEWAY_URL"
    elif echo "$MEM_DOG_API_URL" | grep -q "svc.cluster.local"; then
        MEM_DOG_WEBHOOK_GATEWAY_URL="${MEM_DOG_API_URL}/api/v1/ingest"
        print_success "WEBHOOK_GATEWAY_URL (fallback API ingest): $MEM_DOG_WEBHOOK_GATEWAY_URL"
    else
        GATEWAY_NAME="mem-dog-webhook-gw-${ENVIRONMENT}"
        GATEWAY_HOST=$(gcloud api-gateway gateways describe "$GATEWAY_NAME" \
            --location="$REGION" --project="$PROJECT_ID" \
            --format='value(defaultHostname)' 2>/dev/null || echo "")
        if [ -n "$GATEWAY_HOST" ]; then
            MEM_DOG_WEBHOOK_GATEWAY_URL="https://${GATEWAY_HOST}/webhook"
            print_success "WEBHOOK_GATEWAY_URL (API Gateway): $MEM_DOG_WEBHOOK_GATEWAY_URL"
        else
            MEM_DOG_WEBHOOK_GATEWAY_URL="${MEM_DOG_API_URL}/api/v1/ingest"
            print_success "WEBHOOK_GATEWAY_URL (derived from API URL): $MEM_DOG_WEBHOOK_GATEWAY_URL"
        fi
    fi

    # ── Build and push Docker image ────────────────────────────────────────
    print_info "Building Webhook Gateway Docker image for linux/amd64..."
    cd "$ROOT_DIR"
    docker buildx build \
        --platform linux/amd64 \
        -t "$IMAGE_TAG" \
        --load \
        -f webhook-gateway/Dockerfile \
        webhook-gateway
    print_success "Image built"

    print_info "Pushing image to Artifact Registry..."
    docker push "$IMAGE_TAG"
    print_success "Image pushed"

    # ── Update K8s manifests with real values ──────────────────────────────
    K8S_DIR="$ROOT_DIR/k8s/webhook-gateway"

    # Patch the deployment image
    print_info "Patching deployment image to $IMAGE_TAG..."

    # Apply namespace
    print_info "Applying K8s manifests..."
    kubectl apply -f "$K8S_DIR/namespace.yaml"

    # Create/update the configmap with current values
    kubectl -n webhook-gateway create configmap webhook-gateway-config \
        --from-literal=LLM_PROVIDER="${LLM_PROVIDER:-gemini}" \
        --from-literal=LLM_MODEL="${LLM_MODEL:-}" \
        --from-literal=LLM_API_BASE="${LLM_API_BASE:-}" \
        --from-literal=GEMINI_MODEL="${GEMINI_MODEL}" \
        --from-literal=OTEL_ENABLED="${OTEL_ENABLED:-true}" \
        --from-literal=OTEL_SERVICE_NAME="webhook-gateway" \
        --from-literal=OTEL_EXPORTER_OTLP_PROTOCOL="grpc" \
        --from-literal=LOG_LEVEL="${LOG_LEVEL:-INFO}" \
        --from-literal=DEFAULT_USER_ID="${DEFAULT_USER_ID:-00000000-0000-0000-0000-000000000001}" \
        --from-literal=PORT="8080" \
        --from-literal=MAX_PAYLOAD_BYTES="${MAX_PAYLOAD_BYTES:-1048576}" \
        --from-literal=ZOOM_WS_ENABLED="${ZOOM_WS_ENABLED:-false}" \
        --dry-run=client -o yaml | kubectl apply -f -
    print_success "ConfigMap applied"

    # ── Resolve secrets (env var > GCP Secret Manager) ───────────────────
    _resolve_secret() {
        local var_name="$1" secret_name="$2"
        local val="${!var_name:-}"
        if [ -z "$val" ] && [ -n "$secret_name" ]; then
            val=$(gcloud secrets versions access latest --secret="$secret_name" \
                --project="$PROJECT_ID" 2>/dev/null || echo "")
            if [ -n "$val" ]; then
                print_info "$var_name resolved from Secret Manager ($secret_name)" >&2
            fi
        fi
        printf '%s' "$val"
    }

    GEMINI_KEY_SECRET_NAME="${WGW_GEMINI_KEY_SECRET:-wgw-gemini-api-key-${ENVIRONMENT}}"
    LLM_KEY_SECRET_NAME="${WGW_LLM_KEY_SECRET:-wgw-llm-api-key-${ENVIRONMENT}}"
    WEBHOOK_KEY_SECRET_NAME="${WGW_WEBHOOK_KEY_SECRET:-wgw-webhook-api-key-${ENVIRONMENT}}"

    RESOLVED_GEMINI_API_KEY=$(_resolve_secret GEMINI_API_KEY "$GEMINI_KEY_SECRET_NAME")
    RESOLVED_LLM_API_KEY=$(_resolve_secret LLM_API_KEY "$LLM_KEY_SECRET_NAME")
    RESOLVED_WEBHOOK_API_KEY=$(_resolve_secret MEM_DOG_WEBHOOK_API_KEY "$WEBHOOK_KEY_SECRET_NAME")

    # Auto-discover WEBHOOK_API_KEY from the API service if not resolved above
    if [ -z "$RESOLVED_WEBHOOK_API_KEY" ]; then
        RESOLVED_WEBHOOK_API_KEY=$(gcloud run services describe "mem-dog-api" \
            --region "$REGION" --project "$PROJECT_ID" \
            --format 'value(spec.template.spec.containers[0].env.filter(name=WEBHOOK_GATEWAY_API_KEY).value)' 2>/dev/null || echo "")
        if [ -n "$RESOLVED_WEBHOOK_API_KEY" ]; then
            print_info "WEBHOOK_API_KEY auto-discovered from mem-dog-api service" >&2
        fi
    fi

    # Resolve MEM_DOG_API_KEY for the gateway to authenticate with the mem-dog API
    # (needed for telemetry writes and memory publish)
    local RESOLVED_MEM_DOG_API_KEY="${MEM_DOG_API_KEY:-}"
    if [ -z "$RESOLVED_MEM_DOG_API_KEY" ]; then
        RESOLVED_MEM_DOG_API_KEY=$(kubectl get secret api-auth-secret -n mem-dog \
            -o jsonpath='{.data.API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        [ -n "$RESOLVED_MEM_DOG_API_KEY" ] && print_success "MEM_DOG_API_KEY read from api-auth-secret"
    fi

    # Preserve existing secret values when we have no new value (do not overwrite)
    if kubectl get secret webhook-gateway-secrets -n webhook-gateway &>/dev/null; then
        _b64() { kubectl get secret webhook-gateway-secrets -n webhook-gateway -o jsonpath="{.data.$1}" 2>/dev/null || true; }
        [ -z "${MEM_DOG_API_URL:-}" ] && { val=$(_b64 MEM_DOG_API_URL); [ -n "$val" ] && MEM_DOG_API_URL=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${MEM_DOG_WEBHOOK_GATEWAY_URL:-}" ] && { val=$(_b64 WEBHOOK_GATEWAY_URL); [ -n "$val" ] && MEM_DOG_WEBHOOK_GATEWAY_URL=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "$RESOLVED_WEBHOOK_API_KEY" ] && { val=$(_b64 WEBHOOK_API_KEY); [ -n "$val" ] && RESOLVED_WEBHOOK_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "$RESOLVED_MEM_DOG_API_KEY" ] && { val=$(_b64 MEM_DOG_API_KEY); [ -n "$val" ] && RESOLVED_MEM_DOG_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "$RESOLVED_GEMINI_API_KEY" ] && { val=$(_b64 GEMINI_API_KEY); [ -n "$val" ] && RESOLVED_GEMINI_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "$RESOLVED_LLM_API_KEY" ] && { val=$(_b64 LLM_API_KEY); [ -n "$val" ] && RESOLVED_LLM_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${WGW_API_KEY:-}" ] && { val=$(_b64 WGW_API_KEY); [ -n "$val" ] && WGW_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${OPENAI_API_KEY:-}" ] && { val=$(_b64 OPENAI_API_KEY); [ -n "$val" ] && OPENAI_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${ANTHROPIC_API_KEY:-}" ] && { val=$(_b64 ANTHROPIC_API_KEY); [ -n "$val" ] && ANTHROPIC_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${OPENROUTER_API_KEY:-}" ] && { val=$(_b64 OPENROUTER_API_KEY); [ -n "$val" ] && OPENROUTER_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${ZOOM_CLIENT_ID:-}" ] && { val=$(_b64 ZOOM_CLIENT_ID); [ -n "$val" ] && ZOOM_CLIENT_ID=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${ZOOM_CLIENT_SECRET:-}" ] && { val=$(_b64 ZOOM_CLIENT_SECRET); [ -n "$val" ] && ZOOM_CLIENT_SECRET=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${ZOOM_ACCOUNT_ID:-}" ] && { val=$(_b64 ZOOM_ACCOUNT_ID); [ -n "$val" ] && ZOOM_ACCOUNT_ID=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${ZOOM_SUBSCRIPTION_ID:-}" ] && { val=$(_b64 ZOOM_SUBSCRIPTION_ID); [ -n "$val" ] && ZOOM_SUBSCRIPTION_ID=$(echo "$val" | base64 -d 2>/dev/null); }
        print_info "Preserved existing webhook-gateway-secrets for any unset keys"
    fi

    # Build the kubectl create secret command (only set keys when value is non-empty so we do not overwrite with empty)
    SECRET_CMD=(kubectl -n webhook-gateway create secret generic webhook-gateway-secrets)
    [ -n "${MEM_DOG_API_URL:-}" ] && SECRET_CMD+=("--from-literal=MEM_DOG_API_URL=${MEM_DOG_API_URL}")
    [ -n "${MEM_DOG_WEBHOOK_GATEWAY_URL:-}" ] && SECRET_CMD+=("--from-literal=WEBHOOK_GATEWAY_URL=${MEM_DOG_WEBHOOK_GATEWAY_URL}")
    [ -n "$RESOLVED_WEBHOOK_API_KEY" ] && SECRET_CMD+=("--from-literal=WEBHOOK_API_KEY=${RESOLVED_WEBHOOK_API_KEY}")
    [ -n "$RESOLVED_MEM_DOG_API_KEY" ] && SECRET_CMD+=("--from-literal=MEM_DOG_API_KEY=${RESOLVED_MEM_DOG_API_KEY}")
    [ -n "$RESOLVED_GEMINI_API_KEY" ] && SECRET_CMD+=("--from-literal=GEMINI_API_KEY=${RESOLVED_GEMINI_API_KEY}")
    [ -n "$RESOLVED_LLM_API_KEY" ] && SECRET_CMD+=("--from-literal=LLM_API_KEY=${RESOLVED_LLM_API_KEY}")
    [ -n "${OPENAI_API_KEY:-}" ] && SECRET_CMD+=("--from-literal=OPENAI_API_KEY=${OPENAI_API_KEY}")
    [ -n "${ANTHROPIC_API_KEY:-}" ] && SECRET_CMD+=("--from-literal=ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}")
    [ -n "${OPENROUTER_API_KEY:-}" ] && SECRET_CMD+=("--from-literal=OPENROUTER_API_KEY=${OPENROUTER_API_KEY}")
    [ -n "${WGW_API_KEY:-}" ] && SECRET_CMD+=("--from-literal=WGW_API_KEY=${WGW_API_KEY}")
    [ -n "${ZOOM_CLIENT_ID:-}" ] && SECRET_CMD+=("--from-literal=ZOOM_CLIENT_ID=${ZOOM_CLIENT_ID}")
    [ -n "${ZOOM_CLIENT_SECRET:-}" ] && SECRET_CMD+=("--from-literal=ZOOM_CLIENT_SECRET=${ZOOM_CLIENT_SECRET}")
    [ -n "${ZOOM_ACCOUNT_ID:-}" ] && SECRET_CMD+=("--from-literal=ZOOM_ACCOUNT_ID=${ZOOM_ACCOUNT_ID}")
    [ -n "${ZOOM_SUBSCRIPTION_ID:-}" ] && SECRET_CMD+=("--from-literal=ZOOM_SUBSCRIPTION_ID=${ZOOM_SUBSCRIPTION_ID}")

    # GKE pipeline URLs (auto-discovered from in-cluster services)
    if kubectl get service api -n mem-dog &>/dev/null; then
        SECRET_CMD+=("--from-literal=MEM_DOG_API_GKE_URL=http://api.mem-dog.svc.cluster.local:8080")
    fi
    if kubectl get service webhook-receiver -n webhook-pipeline &>/dev/null; then
        SECRET_CMD+=("--from-literal=WEBHOOK_GKE_RECEIVER_URL=http://webhook-receiver.webhook-pipeline.svc.cluster.local:8080")
    fi

    SECRET_CMD+=(--dry-run=client -o yaml)

    "${SECRET_CMD[@]}" | kubectl apply -f -
    print_success "Secret applied (MEM_DOG_API_URL, WEBHOOK_GATEWAY_URL, API keys)"

    # ── Preserve manually-set env vars across deploy ─────────────────────
    _GW_ENV_PATCH=()
    if kubectl get deployment webhook-gateway -n webhook-gateway &>/dev/null; then
        for _var in NANGO_API_URL NANGO_SECRET_KEY; do
            _val=$(kubectl get deployment webhook-gateway -n webhook-gateway \
                -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name==\"${_var}\")].value}" 2>/dev/null || echo "")
            [ -n "$_val" ] && _GW_ENV_PATCH+=("${_var}=${_val}")
        done
        [ ${#_GW_ENV_PATCH[@]} -gt 0 ] && print_info "Will preserve ${#_GW_ENV_PATCH[@]} gateway env vars after apply"
    fi

    # Apply deployment with patched image
    kubectl apply -f "$K8S_DIR/service.yaml"
    # Patch the image in the deployment YAML before applying so pods pull the correct image immediately
    sed "s|image: webhook-gateway:latest|image: ${IMAGE_TAG}|" "$K8S_DIR/deployment.yaml" \
        | kubectl apply -f -
    print_success "Deployment applied (image: $IMAGE_TAG)"

    # ── Re-apply preserved env vars ───────────────────────────────────────
    if [ ${#_GW_ENV_PATCH[@]} -gt 0 ]; then
        kubectl set env deployment/webhook-gateway -n webhook-gateway "${_GW_ENV_PATCH[@]}"
        print_success "Preserved gateway env vars: ${_GW_ENV_PATCH[*]}"
    fi

    # Apply Gateway and HTTPRoute
    kubectl apply -f "$K8S_DIR/gateway.yaml"
    kubectl apply -f "$K8S_DIR/httproute.yaml"
    print_success "Gateway (open-jaws) and HTTPRoute applied"

    # ── Wait for rollout ───────────────────────────────────────────────────
    print_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/webhook-gateway -n webhook-gateway --timeout=120s
    print_success "Rollout complete"

    # ── Get Gateway address ────────────────────────────────────────────────
    print_info "Retrieving open-jaws Gateway address..."
    GW_IP=""
    for i in $(seq 1 12); do
        GW_IP=$(kubectl get gateway open-jaws -n webhook-gateway \
            -o jsonpath='{.status.addresses[0].value}' 2>/dev/null || echo "")
        if [ -n "$GW_IP" ]; then
            break
        fi
        print_info "Waiting for Gateway IP assignment (attempt $i/12)..."
        sleep 10
    done

    print_header "Webhook Gateway Deployed to GKE"
    echo "Project:            $PROJECT_ID"
    echo "Cluster:            $GKE_CLUSTER"
    echo "Namespace:          webhook-gateway"
    echo "Gateway:            open-jaws"
    echo "Image:              $IMAGE_TAG"
    echo ""
    echo "Communication:"
    echo "  MEM_DOG_API_URL:    $MEM_DOG_API_URL"
    echo "  WEBHOOK_GATEWAY:    $MEM_DOG_WEBHOOK_GATEWAY_URL"
    echo "  WEBHOOK_API_KEY:    $([ -n "$RESOLVED_WEBHOOK_API_KEY" ] && echo "set" || echo "NOT SET — webhooks will fail")"
    echo ""
    echo "LLM:"
    echo "  Provider:           ${LLM_PROVIDER:-gemini}"
    echo "  Model:              ${LLM_MODEL:-${GEMINI_MODEL}}"
    echo "  GEMINI_API_KEY:     $([ -n "$RESOLVED_GEMINI_API_KEY" ] && echo "set" || echo "not set")"
    echo "  LLM_API_KEY:        $([ -n "$RESOLVED_LLM_API_KEY" ] && echo "set" || echo "not set")"
    echo ""
    echo "Zoom WebSocket:"
    echo "  ZOOM_WS_ENABLED:    ${ZOOM_WS_ENABLED:-false}"
    echo "  ZOOM_CLIENT_ID:     $([ -n "${ZOOM_CLIENT_ID:-}" ] && echo "set" || echo "not set")"
    echo "  ZOOM_SUBSCRIPTION:  $([ -n "${ZOOM_SUBSCRIPTION_ID:-}" ] && echo "set" || echo "not set")"
    echo ""
    if [ -n "$GW_IP" ]; then
        echo "Gateway IP:         $GW_IP"
        echo ""
        echo "Endpoints (once DNS is configured):"
        echo "  Swagger docs:  https://YOUR_DOMAIN/docs"
        echo "  Webhooks:      https://YOUR_DOMAIN/webhooks/{channel_type}"
        echo "  Health:        https://YOUR_DOMAIN/health"
        echo "  Providers:     https://YOUR_DOMAIN/providers"
        echo ""
        echo "Quick test (via IP):"
        echo "  curl http://$GW_IP/health"
    else
        print_warning "Gateway IP not yet assigned — check: kubectl get gateway open-jaws -n webhook-gateway"
    fi
    echo ""
    echo "Useful commands:"
    echo "  kubectl get pods -n webhook-gateway"
    echo "  kubectl logs -n webhook-gateway -l app=webhook-gateway --tail=50"
    echo "  kubectl get gateway open-jaws -n webhook-gateway"
}

# =============================================================================
# Deploy OpenClaw Node.js to GKE
# =============================================================================

deploy_openclaw_node_gke() {
    print_header "Deploying OpenClaw Node.js to GKE: $ENVIRONMENT"

    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/openclaw-node:${ENVIRONMENT}-latest"
    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    # ── Verify GKE cluster ─────────────────────────────────────────────────
    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    # ── Build and push Docker image ────────────────────────────────────────
    print_info "Building OpenClaw Node.js Docker image for linux/amd64..."
    cd "$ROOT_DIR"
    docker buildx build \
        --no-cache \
        --platform linux/amd64 \
        -t "$IMAGE_TAG" \
        --load \
        -f openclaw-node/Dockerfile \
        openclaw-node
    print_success "Image built"

    print_info "Pushing image to Artifact Registry..."
    docker push "$IMAGE_TAG"
    print_success "Image pushed"

    # ── Resolve secrets (env var > GCP Secret Manager) ───────────────────
    GEMINI_KEY_SECRET_NAME="${WGW_GEMINI_KEY_SECRET:-wgw-gemini-api-key-${ENVIRONMENT}}"
    RESOLVED_GEMINI_API_KEY="${GEMINI_API_KEY:-}"
    if [ -z "$RESOLVED_GEMINI_API_KEY" ] && [ -n "$GEMINI_KEY_SECRET_NAME" ]; then
        RESOLVED_GEMINI_API_KEY=$(gcloud secrets versions access latest --secret="$GEMINI_KEY_SECRET_NAME" \
            --project="$PROJECT_ID" 2>/dev/null || echo "")
        [ -n "$RESOLVED_GEMINI_API_KEY" ] && print_info "GEMINI_API_KEY resolved from Secret Manager ($GEMINI_KEY_SECRET_NAME)"
    fi

    # Preserve existing secret values when we have no new value
    if kubectl get secret openclaw-node-secrets -n webhook-gateway &>/dev/null; then
        _b64_node() { kubectl get secret openclaw-node-secrets -n webhook-gateway -o jsonpath="{.data.$1}" 2>/dev/null || true; }
        [ -z "$RESOLVED_GEMINI_API_KEY" ] && { val=$(_b64_node GEMINI_API_KEY); [ -n "$val" ] && RESOLVED_GEMINI_API_KEY=$(echo "$val" | base64 -d 2>/dev/null); }
        [ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ] && { val=$(_b64_node OPENCLAW_GATEWAY_TOKEN); [ -n "$val" ] && OPENCLAW_GATEWAY_TOKEN=$(echo "$val" | base64 -d 2>/dev/null); }
        print_info "Preserved existing openclaw-node-secrets for any unset keys"
    fi

    # Build secret
    SECRET_CMD=(kubectl -n webhook-gateway create secret generic openclaw-node-secrets)
    [ -n "$RESOLVED_GEMINI_API_KEY" ] && SECRET_CMD+=("--from-literal=GEMINI_API_KEY=${RESOLVED_GEMINI_API_KEY}")
    [ -n "${OPENCLAW_GATEWAY_TOKEN:-}" ] && SECRET_CMD+=("--from-literal=OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN}")
    SECRET_CMD+=(--dry-run=client -o yaml)
    "${SECRET_CMD[@]}" | kubectl apply -f -
    print_success "Secret applied"

    # ── Apply K8s manifests ────────────────────────────────────────────────
    K8S_DIR="$ROOT_DIR/k8s/openclaw-node"

    print_info "Applying K8s manifests..."

    # Create/update configmap with current values
    kubectl -n webhook-gateway create configmap openclaw-node-config \
        --from-literal=GEMINI_MODEL="${GEMINI_MODEL}" \
        --from-literal=MEM_DOG_API_URL="http://api.mem-dog.svc.cluster.local:8080" \
        --from-literal=WEBHOOK_BRIDGE_URL="http://webhook-gateway.webhook-gateway.svc.cluster.local:8080/webhooks/openclaw" \
        --from-literal=LOG_LEVEL="${LOG_LEVEL:-info}" \
        --dry-run=client -o yaml | kubectl apply -f -
    print_success "ConfigMap applied"

    kubectl apply -f "$K8S_DIR/service.yaml"

    # Patch the image in the deployment YAML before applying
    sed "s|image: openclaw-node:latest|image: ${IMAGE_TAG}|" "$K8S_DIR/deployment.yaml" \
        | kubectl apply -f -
    print_success "Deployment applied (image: $IMAGE_TAG)"

    kubectl apply -f "$K8S_DIR/httproute.yaml"
    print_success "HTTPRoute applied (/oc/* → openclaw-node:18789)"

    # ── Wait for rollout ───────────────────────────────────────────────────
    print_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/openclaw-node -n webhook-gateway --timeout=120s
    print_success "Rollout complete"

    # ── Summary ──────────────────────────────────────────────────────────
    print_header "OpenClaw Node.js Deployed to GKE"
    echo "Project:            $PROJECT_ID"
    echo "Cluster:            $GKE_CLUSTER"
    echo "Namespace:          webhook-gateway"
    echo "Image:              $IMAGE_TAG"
    echo ""
    echo "Route:              /oc/* → openclaw-node:18789 (prefix stripped)"
    echo "Bridge target:      webhook-gateway:8080/webhooks/openclaw"
    echo ""
    echo "Quick test:"
    echo "  curl http://34.49.247.205/oc/healthz"
    echo ""
    echo "Useful commands:"
    echo "  kubectl get pods -n webhook-gateway -l app=openclaw-node"
    echo "  kubectl logs -n webhook-gateway -l app=openclaw-node --tail=50"
}

# =============================================================================
# Deploy API to GKE
# =============================================================================

deploy_api_gke() {
    print_header "Deploying mem-dog API to GKE: $ENVIRONMENT"

    local K8S_DIR="k8s"
    local IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/api:${ENVIRONMENT}-gke-latest"
    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    # ── Verify GKE cluster ──────────────────────────────────────────────────
    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    # ── Build and push API image ────────────────────────────────────────────
    print_info "Building API image: $IMAGE_TAG"
    docker build --no-cache --platform linux/amd64 -t "$IMAGE_TAG" api/
    docker push "$IMAGE_TAG"
    print_success "API image pushed: $IMAGE_TAG"

    # ── Ensure namespace ────────────────────────────────────────────────────
    kubectl create namespace mem-dog --dry-run=client -o yaml | kubectl apply -f -

    # ── Workload Identity setup ─────────────────────────────────────────────
    local GKE_API_GSA="mem-dog-api-gke-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    local GKE_API_KSA="api-sa"
    local GKE_API_KSA_NS="mem-dog"

    print_info "Setting up Workload Identity..."
    gcloud iam service-accounts create "mem-dog-api-gke-${ENVIRONMENT}" \
        --project="$PROJECT_ID" \
        --display-name="mem-dog API GKE ($ENVIRONMENT)" 2>/dev/null || true

    # Grant storage access for GCS buckets
    local GCS_BUCKETS=(
        "${PROJECT_ID}-mem-dog-raw-${ENVIRONMENT}"
        "${PROJECT_ID}-mem-dog-meta-${ENVIRONMENT}"
        "${PROJECT_ID}-mem-dog-memories-${ENVIRONMENT}"
        "${PROJECT_ID}-mem-dog-users-${ENVIRONMENT}"
        "${PROJECT_ID}-mem-dog-config-${ENVIRONMENT}"
    )
    for BUCKET in "${GCS_BUCKETS[@]}"; do
        gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
            --member="serviceAccount:${GKE_API_GSA}" \
            --role="roles/storage.objectAdmin" --quiet 2>/dev/null || true
    done
    print_success "GCS bucket permissions granted (${#GCS_BUCKETS[@]} buckets)"

    # Workload Identity binding
    gcloud iam service-accounts add-iam-policy-binding "$GKE_API_GSA" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${GKE_API_KSA_NS}/${GKE_API_KSA}]" \
        --role="roles/iam.workloadIdentityUser" --quiet 2>/dev/null || true
    print_success "Workload Identity binding set"

    # Apply SA manifest and annotate
    kubectl apply -f "$K8S_DIR/api-sa.yaml"
    kubectl annotate serviceaccount "$GKE_API_KSA" -n "$GKE_API_KSA_NS" \
        "iam.gke.io/gcp-service-account=${GKE_API_GSA}" --overwrite
    print_success "Kubernetes ServiceAccount annotated"

    # ── Resolve Supabase service role key ────────────────────────────────────
    local SUPABASE_SERVICE_KEY=""
    if kubectl get secret supabase-secrets -n supabase &>/dev/null; then
        SUPABASE_SERVICE_KEY=$(kubectl get secret supabase-secrets -n supabase \
            -o jsonpath='{.data.SERVICE_ROLE_KEY}' | base64 -d 2>/dev/null || echo "")
    fi
    if [ -z "$SUPABASE_SERVICE_KEY" ]; then
        print_warning "Supabase SERVICE_ROLE_KEY not found — deploy-supabase-gke first or set SUPABASE_SERVICE_ROLE_KEY"
        SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-placeholder}"
    fi

    # ── Resolve Supabase JWT secret (for browser auth) ─────────────────────
    local SUPABASE_JWT=""
    if kubectl get secret supabase-secrets -n supabase &>/dev/null; then
        SUPABASE_JWT=$(kubectl get secret supabase-secrets -n supabase \
            -o jsonpath='{.data.JWT_SECRET}' | base64 -d 2>/dev/null || echo "")
    fi

    # ── Create/update API secrets ────────────────────────────────────────────
    kubectl -n mem-dog create secret generic api-supabase-secrets \
        --from-literal=SUPABASE_KEY="$SUPABASE_SERVICE_KEY" \
        --from-literal=SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_KEY" \
        --from-literal=SUPABASE_JWT_SECRET="${SUPABASE_JWT:-}" \
        --dry-run=client -o yaml | kubectl apply -f -
    print_success "api-supabase-secrets applied"

    # ── Update ConfigMap for Supabase + GCS ──────────────────────────────────
    local RAW_BUCKET_NAME="${PROJECT_ID}-mem-dog-raw-${ENVIRONMENT}"
    local META_BUCKET_NAME="${PROJECT_ID}-mem-dog-meta-${ENVIRONMENT}"
    local MEMORIES_BUCKET_NAME="${PROJECT_ID}-mem-dog-memories-${ENVIRONMENT}"
    local USER_BUCKET_NAME="${PROJECT_ID}-mem-dog-users-${ENVIRONMENT}"
    local CONFIG_BUCKET="${PROJECT_ID}-mem-dog-config-${ENVIRONMENT}"

    local CONFIGMAP_EXTRA=()
    if kubectl get service webhook-receiver -n webhook-pipeline &>/dev/null; then
        CONFIGMAP_EXTRA+=(
            --from-literal=WEBHOOK_GATEWAY_URL="http://webhook-receiver.webhook-pipeline.svc.cluster.local:8080"
            --from-literal=WEBHOOK_API_KEY="${MEM_DOG_WEBHOOK_API_KEY:-gke-internal}"
        )
        print_success "Webhook receiver found — wiring WEBHOOK_GATEWAY_URL for API → pipeline forwarding"
    else
        # Preserve existing API webhook config so re-deploy does not clear it
        if kubectl get configmap api-config -n mem-dog &>/dev/null; then
            existing_url=$(kubectl get configmap api-config -n mem-dog -o jsonpath='{.data.WEBHOOK_GATEWAY_URL}' 2>/dev/null || true)
            existing_key=$(kubectl get configmap api-config -n mem-dog -o jsonpath='{.data.WEBHOOK_API_KEY}' 2>/dev/null || true)
            [ -n "$existing_url" ] && CONFIGMAP_EXTRA+=(--from-literal=WEBHOOK_GATEWAY_URL="$existing_url")
            [ -n "$existing_key" ] && CONFIGMAP_EXTRA+=(--from-literal=WEBHOOK_API_KEY="$existing_key")
            [ ${#CONFIGMAP_EXTRA[@]} -gt 0 ] && print_info "Preserved existing API WEBHOOK_GATEWAY_URL/WEBHOOK_API_KEY from configmap"
        fi
        [ ${#CONFIGMAP_EXTRA[@]} -eq 0 ] && print_info "Webhook receiver not found (run deploy-webhook-pipeline-gke first for API→receiver forwarding)"
    fi

    kubectl -n mem-dog create configmap api-config \
        --from-literal=STORAGE_BACKEND="supabase" \
        --from-literal=SUPABASE_URL="http://supabase-kong.supabase.svc.cluster.local:8000" \
        --from-literal=GCP_PROJECT_ID="$PROJECT_ID" \
        --from-literal=SYSTEM_CONFIG_BUCKET="$CONFIG_BUCKET" \
        --from-literal=RAW_BUCKET="$RAW_BUCKET_NAME" \
        --from-literal=META_BUCKET="$META_BUCKET_NAME" \
        --from-literal=MEMORIES_BUCKET="$MEMORIES_BUCKET_NAME" \
        --from-literal=USER_BUCKET="$USER_BUCKET_NAME" \
        --from-literal=MEM_DOG_DATA_DIR="/data" \
        --from-literal=ENVIRONMENT="$ENVIRONMENT" \
        --from-literal=LOG_LEVEL="${LOG_LEVEL:-INFO}" \
        --from-literal=OLLAMA_LOCAL_API_BASE="http://ollama.webhook-pipeline.svc.cluster.local:11434" \
        --from-literal=OLLAMA_LOCAL_MODEL_EMBEDDING="embeddinggemma" \
        "${CONFIGMAP_EXTRA[@]}" \
        --dry-run=client -o yaml | kubectl apply -f -
    print_success "ConfigMap applied (STORAGE_BACKEND=supabase, RAW_BUCKET=$RAW_BUCKET_NAME)"

    # ── Preserve API keys from existing API deployment (models come from ai.env) ──
    local _API_ENV_PATCH=()
    if kubectl get deployment api -n mem-dog &>/dev/null; then
        for _var in SYSTEM_GEMINI_API_KEY GEMINI_API_KEY SUPABASE_API_GATEWAY_KEY NANGO_API_URL NANGO_SECRET_KEY NANGO_SERVER_URL NANGO_PUBLIC_KEY GEMINI_MODEL ZOOM_WEBHOOK_SECRET; do
            _val=$(kubectl get deployment api -n mem-dog \
                -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name==\"${_var}\")].value}" 2>/dev/null || echo "")
            [ -n "$_val" ] && _API_ENV_PATCH+=("${_var}=${_val}")
        done
        [ ${#_API_ENV_PATCH[@]} -gt 0 ] && print_info "Will preserve ${#_API_ENV_PATCH[@]} API env vars after apply"
    fi

    # ── Apply remaining manifests ────────────────────────────────────────────
    kubectl apply -f "$K8S_DIR/api-pvc.yaml"
    sed "s|image: mem-dog-api|image: ${IMAGE_TAG}|" "$K8S_DIR/api-deployment.yaml" \
        | kubectl apply -f -
    kubectl apply -f "$K8S_DIR/api-service.yaml"
    print_success "API deployment and service applied"

    # ── Re-apply preserved env vars ───────────────────────────────────────
    if [ ${#_API_ENV_PATCH[@]} -gt 0 ]; then
        kubectl set env deployment/api -n mem-dog "${_API_ENV_PATCH[@]}"
        print_success "Preserved API env vars: ${_API_ENV_PATCH[*]}"
    fi

    # ── Force pod restart to pick up new image (tag is reused) ────────────
    kubectl rollout restart deployment/api -n mem-dog

    # ── Wait for rollout ─────────────────────────────────────────────────────
    print_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/api -n mem-dog --timeout=120s
    print_success "Rollout complete"

    print_header "mem-dog API Deployed to GKE"
    echo "Image:     $IMAGE_TAG"
    echo "Namespace: mem-dog"
    echo "Service:   api.mem-dog.svc.cluster.local:8080"
    echo ""
    echo "Quick test:"
    echo "  kubectl port-forward svc/api -n mem-dog 9091:8080 &"
    echo "  curl http://localhost:9091/health"
    echo "  curl -X POST http://localhost:9091/api/v1/users -H 'Content-Type: application/json' -d '{\"username\":\"test\",\"email\":\"t@t.com\"}'"
}

# =============================================================================
# Restart all GKE workloads (rollout restart)
# =============================================================================

restart_gke() {
    print_header "Restarting all GKE workloads"

    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    local NAMESPACES=(mem-dog webhook-gateway webhook-pipeline supabase)
    for NS in "${NAMESPACES[@]}"; do
        if ! kubectl get namespace "$NS" &>/dev/null; then
            print_info "Namespace $NS does not exist — skipping"
            continue
        fi
        print_info "Restarting deployments in $NS..."
        for DEP in $(kubectl get deployment -n "$NS" -o name 2>/dev/null); do
            kubectl rollout restart "$DEP" -n "$NS"
            print_success "  restarted $DEP"
        done
        print_info "Restarting statefulsets in $NS..."
        for STS in $(kubectl get statefulset -n "$NS" -o name 2>/dev/null); do
            kubectl rollout restart "$STS" -n "$NS"
            print_success "  restarted $STS"
        done
    done

    print_header "Waiting for rollouts to complete"
    for NS in "${NAMESPACES[@]}"; do
        if ! kubectl get namespace "$NS" &>/dev/null; then
            continue
        fi
        for DEP in $(kubectl get deployment -n "$NS" -o name 2>/dev/null); do
            kubectl rollout status "$DEP" -n "$NS" --timeout=120s 2>/dev/null || true
        done
        for STS in $(kubectl get statefulset -n "$NS" -o name 2>/dev/null); do
            kubectl rollout status "$STS" -n "$NS" --timeout=180s 2>/dev/null || true
        done
    done
    print_success "All GKE workloads restarted"
}

# =============================================================================
# Deploy Webhook Pipeline to GKE
# =============================================================================

deploy_webhook_pipeline_gke() {
    print_header "Deploying Webhook Pipeline to GKE (NATS): $ENVIRONMENT"

    local K8S_DIR="k8s/webhook-pipeline"
    local RECEIVER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/webhook-receiver:${ENVIRONMENT}-gke-latest"
    local AGENT_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/webhook-agent:${ENVIRONMENT}-gke-latest"
    local PULL_WORKER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/webhook-pull-worker:${ENVIRONMENT}-gke-latest"
    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    local PIPELINE_NS="webhook-pipeline"
    local NATS_URL="nats://nats.${PIPELINE_NS}.svc.cluster.local:4222"

    # ── Verify GKE cluster ──────────────────────────────────────────────────
    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    # ── Build and push images ───────────────────────────────────────────────
    print_info "Building webhook receiver image..."
    docker build --no-cache --platform linux/amd64 -t "$RECEIVER_IMAGE" -f webhook/receiver/Dockerfile.gke webhook/receiver/
    docker push "$RECEIVER_IMAGE"
    print_success "Receiver image pushed"

    print_info "Building webhook agent image..."
    docker build --no-cache --platform linux/amd64 \
      --build-arg "INSTALL_DOCLING=${INSTALL_DOCLING:-false}" \
      -t "$AGENT_IMAGE" -f webhook/processor/Dockerfile webhook/processor/
    docker push "$AGENT_IMAGE"
    print_success "Agent image pushed"

    print_info "Building webhook pull-worker image..."
    docker build --no-cache --platform linux/amd64 -t "$PULL_WORKER_IMAGE" -f webhook/processor/Dockerfile.pull-worker webhook/processor/
    docker push "$PULL_WORKER_IMAGE"
    print_success "Pull-worker image pushed"

    # ── Workload Identity setup ─────────────────────────────────────────────
    local WH_GSA="mem-dog-webhook-gke-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    local WH_KSA="webhook-pipeline-sa"

    print_info "Setting up Workload Identity for webhook pipeline..."
    gcloud iam service-accounts create "mem-dog-webhook-gke-${ENVIRONMENT}" \
        --project="$PROJECT_ID" \
        --display-name="mem-dog Webhook Pipeline GKE ($ENVIRONMENT)" 2>/dev/null || true

    # Grant Storage and Vertex AI access (no Pub/Sub needed — using in-cluster NATS)
    for ROLE in roles/storage.objectAdmin roles/aiplatform.user; do
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:${WH_GSA}" \
            --role="$ROLE" --quiet 2>/dev/null || true
    done

    # Ensure namespace exists
    kubectl create namespace "$PIPELINE_NS" --dry-run=client -o yaml | kubectl apply -f -

    # Workload Identity binding
    gcloud iam service-accounts add-iam-policy-binding "$WH_GSA" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${PIPELINE_NS}/${WH_KSA}]" \
        --role="roles/iam.workloadIdentityUser" --quiet 2>/dev/null || true
    print_success "Workload Identity binding set"

    # ── Resolve secrets (LLM keys, API URL) ─────────────────────────────────
    local GOOGLE_API_KEY=""
    GOOGLE_API_KEY=$(gcloud secrets versions access latest \
        --secret="GEMINI_API_KEY" --project="$PROJECT_ID" 2>/dev/null || echo "")
    if [ -z "$GOOGLE_API_KEY" ]; then
        GOOGLE_API_KEY="${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}"
    fi
    # Fallback: read from api-auth-secret in mem-dog namespace
    if [ -z "$GOOGLE_API_KEY" ]; then
        GOOGLE_API_KEY=$(kubectl get secret api-auth-secret -n mem-dog \
            -o jsonpath='{.data.SYSTEM_GEMINI_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        [ -n "$GOOGLE_API_KEY" ] && print_success "Gemini API key read from api-auth-secret"
    fi
    # Fallback: preserve existing key from webhook-pipeline-secrets
    if [ -z "$GOOGLE_API_KEY" ]; then
        GOOGLE_API_KEY=$(kubectl get secret webhook-pipeline-secrets -n "$PIPELINE_NS" \
            -o jsonpath='{.data.GOOGLE_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        [ -n "$GOOGLE_API_KEY" ] && print_info "Preserved existing GOOGLE_API_KEY from webhook-pipeline-secrets"
    fi

    local MEM_DOG_API_GKE_URL="http://api.mem-dog.svc.cluster.local:8080"

    # ── Deploy NATS server ──────────────────────────────────────────────────
    print_info "Deploying in-cluster NATS server..."
    kubectl apply -f "$K8S_DIR/nats-deployment.yaml"
    kubectl apply -f "$K8S_DIR/nats-service.yaml"
    kubectl rollout status deployment/nats -n "$PIPELINE_NS" --timeout=60s || true
    print_success "NATS server deployed"

    # ── Deploy Ollama embedding server ────────────────────────────────────
    print_info "Deploying Ollama embedding server..."
    kubectl apply -f "$K8S_DIR/ollama-deployment.yaml"
    kubectl apply -f "$K8S_DIR/ollama-service.yaml"
    print_success "Ollama embedding server deployed"

    # ── Apply K8s manifests ─────────────────────────────────────────────────
    kubectl apply -f "$K8S_DIR/sa.yaml"
    kubectl annotate serviceaccount "$WH_KSA" -n "$PIPELINE_NS" \
        "iam.gke.io/gcp-service-account=${WH_GSA}" --overwrite

    # ConfigMap (NATS instead of Pub/Sub)
    # Model defaults come from config/ai.env (sourced at script start); no cluster preservation needed.
    local PIPELINE_ADK_MODEL="${ADK_MODEL:-${GEMINI_LITELLM_MODEL}}"
    local PIPELINE_GEMINI_MODEL="${GEMINI_LITELLM_MODEL}"
    local PIPELINE_FALLBACK="${DATA_PIPELINE_AI_FALLBACK_MODEL:-${FALLBACK_LITELLM_MODEL}}"
    local PIPELINE_PREFER_GEMINI="${AGENT_PREFER_GEMINI:-false}"
    local PIPELINE_OC_SMALL="${OLLAMA_CLOUD_MODEL_SMALL:-ollama/gemma3:4b}"
    local PIPELINE_OC_MEDIUM="${OLLAMA_CLOUD_MODEL_MEDIUM:-ollama/gemma3:12b}"
    local PIPELINE_OC_LARGE="${OLLAMA_CLOUD_MODEL_LARGE:-ollama/gemma3:27b}"
    local PIPELINE_OC_MULTIMODAL="${OLLAMA_CLOUD_MODEL_MULTIMODAL:-ollama/qwen3-vl:235b-cloud}"
    local PIPELINE_OC_OMNI="${OLLAMA_CLOUD_MODEL_OMNI:-ollama/qwen3.5:cloud}"

    kubectl -n "$PIPELINE_NS" create configmap webhook-pipeline-config \
        --from-literal=GCP_PROJECT_ID="$PROJECT_ID" \
        --from-literal=NATS_URL="$NATS_URL" \
        --from-literal=NATS_SUBJECT="webhook.inbound" \
        --from-literal=MEM_DOG_API_URL="$MEM_DOG_API_GKE_URL" \
        --from-literal=AGENT_URL="http://webhook-agent.${PIPELINE_NS}.svc.cluster.local:8080" \
        --from-literal=ENVIRONMENT="$ENVIRONMENT" \
        --from-literal=MAX_PAYLOAD_BYTES="1048576" \
        --from-literal=ADK_MODEL="$PIPELINE_ADK_MODEL" \
        --from-literal=GEMINI_MODEL="$PIPELINE_GEMINI_MODEL" \
        --from-literal=DATA_PIPELINE_AI_FALLBACK_MODEL="$PIPELINE_FALLBACK" \
        --from-literal=AGENT_PREFER_GEMINI="$PIPELINE_PREFER_GEMINI" \
        --from-literal=OLLAMA_CLOUD_MODEL_SMALL="$PIPELINE_OC_SMALL" \
        --from-literal=OLLAMA_CLOUD_MODEL_MEDIUM="$PIPELINE_OC_MEDIUM" \
        --from-literal=OLLAMA_CLOUD_MODEL_LARGE="$PIPELINE_OC_LARGE" \
        --from-literal=OLLAMA_CLOUD_MODEL_MULTIMODAL="$PIPELINE_OC_MULTIMODAL" \
        --from-literal=OLLAMA_CLOUD_MODEL_OMNI="$PIPELINE_OC_OMNI" \
        --from-literal=OLLAMA_LOCAL_API_BASE="http://ollama.webhook-pipeline.svc.cluster.local:11434" \
        --from-literal=OLLAMA_LOCAL_MODEL_EMBEDDING="embeddinggemma" \
        --dry-run=client -o yaml | kubectl apply -f -
    print_success "ConfigMap applied (NATS_URL=$NATS_URL, ADK_MODEL=$PIPELINE_ADK_MODEL, prefer_gemini=$PIPELINE_PREFER_GEMINI)"

    # Resolve API key for the webhook agent to authenticate with mem-dog API
    local WH_API_KEY="${MEM_DOG_API_KEY:-}"
    if [ -z "$WH_API_KEY" ]; then
        WH_API_KEY=$(kubectl get secret api-auth-secret -n mem-dog \
            -o jsonpath='{.data.API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        [ -n "$WH_API_KEY" ] && print_success "API key read from api-auth-secret"
    fi

    # Secrets (includes Ollama Cloud API key for primary inference when set)
    # Preserve existing OLLAMA_CLOUD_API_KEY from the cluster if not explicitly set
    local OC_API_KEY="${OLLAMA_CLOUD_API_KEY:-${OLLAMA_API_KEY:-}}"
    if [ -z "$OC_API_KEY" ]; then
        OC_API_KEY=$(kubectl -n "$PIPELINE_NS" get secret webhook-pipeline-secrets \
            -o jsonpath='{.data.OLLAMA_CLOUD_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        [ -n "$OC_API_KEY" ] && print_success "Preserved existing OLLAMA_CLOUD_API_KEY from cluster"
    fi
    kubectl -n "$PIPELINE_NS" create secret generic webhook-pipeline-secrets \
        --from-literal=GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
        --from-literal=MEM_DOG_API_KEY="${WH_API_KEY}" \
        --from-literal=OLLAMA_CLOUD_API_KEY="${OC_API_KEY}" \
        --dry-run=client -o yaml | kubectl apply -f -
    print_success "Secrets applied"
    [ -n "$OC_API_KEY" ] && print_success "Ollama Cloud API key wired for primary inference"

    # Receiver
    sed "s|image: webhook-receiver|image: ${RECEIVER_IMAGE}|" "$K8S_DIR/receiver-deployment.yaml" \
        | kubectl apply -f -
    kubectl apply -f "$K8S_DIR/receiver-service.yaml"
    print_success "Receiver deployment and service applied"

    # Pull worker (NATS subscriber)
    sed "s|image: webhook-pull-worker|image: ${PULL_WORKER_IMAGE}|" "$K8S_DIR/processor-deployment.yaml" \
        | kubectl apply -f -
    print_success "Pull-worker (NATS subscriber) deployment applied"

    # Agent
    # Preserve custom env vars (VIEWPOINT_PROMPT_ID, AI_EMBEDDING_MODEL) from existing deployment
    local _VIEWPOINT_PROMPT_ID="${VIEWPOINT_PROMPT_ID:-}"
    local _AI_EMBEDDING_MODEL="${AI_EMBEDDING_MODEL:-}"
    if [ -z "$_VIEWPOINT_PROMPT_ID" ] && kubectl get deployment webhook-agent -n "$PIPELINE_NS" &>/dev/null; then
        _VIEWPOINT_PROMPT_ID=$(kubectl get deployment webhook-agent -n "$PIPELINE_NS" \
            -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="VIEWPOINT_PROMPT_ID")].value}' 2>/dev/null || echo "")
    fi
    if [ -z "$_AI_EMBEDDING_MODEL" ] && kubectl get deployment webhook-agent -n "$PIPELINE_NS" &>/dev/null; then
        _AI_EMBEDDING_MODEL=$(kubectl get deployment webhook-agent -n "$PIPELINE_NS" \
            -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="AI_EMBEDDING_MODEL")].value}' 2>/dev/null || echo "")
    fi

    sed "s|image: webhook-agent|image: ${AGENT_IMAGE}|" "$K8S_DIR/agent-deployment.yaml" \
        | kubectl apply -f -

    # Re-apply preserved env vars on the deployment
    local AGENT_ENV_PATCH=()
    [ -n "$_VIEWPOINT_PROMPT_ID" ] && AGENT_ENV_PATCH+=("VIEWPOINT_PROMPT_ID=$_VIEWPOINT_PROMPT_ID")
    [ -n "$_AI_EMBEDDING_MODEL" ] && AGENT_ENV_PATCH+=("AI_EMBEDDING_MODEL=$_AI_EMBEDDING_MODEL")
    if [ ${#AGENT_ENV_PATCH[@]} -gt 0 ]; then
        kubectl set env deployment/webhook-agent -n "$PIPELINE_NS" "${AGENT_ENV_PATCH[@]}"
        print_info "Preserved agent env vars: ${AGENT_ENV_PATCH[*]}"
    fi

    kubectl apply -f "$K8S_DIR/agent-service.yaml"
    print_success "Agent deployment and service applied"

    # ── Force pod restart to pick up new images (tags are reused) ───────────
    kubectl rollout restart deployment/webhook-receiver -n "$PIPELINE_NS"
    kubectl rollout restart deployment/webhook-agent -n "$PIPELINE_NS"
    kubectl rollout restart deployment/webhook-pull-worker -n "$PIPELINE_NS"

    # ── Wait for rollout ─────────────────────────────────────────────────────
    print_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/webhook-receiver -n "$PIPELINE_NS" --timeout=120s || true
    kubectl rollout status deployment/webhook-agent -n "$PIPELINE_NS" --timeout=120s || true
    kubectl rollout status deployment/webhook-pull-worker -n "$PIPELINE_NS" --timeout=120s || true

    print_header "Webhook Pipeline Deployed to GKE (NATS)"
    echo "Namespace:    $PIPELINE_NS"
    echo "Message bus:  NATS (in-cluster) — $NATS_URL"
    echo "Subject:      webhook.inbound"
    echo "Receiver:     webhook-receiver.${PIPELINE_NS}.svc.cluster.local:8080"
    echo "Agent:        webhook-agent.${PIPELINE_NS}.svc.cluster.local:8080"
    echo ""
    echo "Quick test:"
    echo "  kubectl port-forward svc/webhook-receiver -n $PIPELINE_NS 9092:8080 &"
    echo "  curl -X POST http://localhost:9092/ -H 'Content-Type: application/json' -d '{\"message\":\"test\"}'"
    echo ""
    echo "Pods:"
    kubectl get pods -n "$PIPELINE_NS"
}

# =============================================================================
# MCP Server (GKE)
# =============================================================================

deploy_mcp_server_gke() {
    print_header "Deploying MCP Server to GKE: $ENVIRONMENT"

    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/mem-dog/mcp-server:${ENVIRONMENT}-gke-latest"
    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    # ── Verify GKE cluster ─────────────────────────────────────────────────
    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            echo ""
            echo "Set GKE_CLUSTER and GKE_ZONE:"
            echo "  GKE_CLUSTER=my-cluster GKE_ZONE=${REGION}-a $0 deploy-mcp-server-gke -p $PROJECT_ID -e $ENVIRONMENT"
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    if ! command -v kubectl &>/dev/null; then
        print_error "kubectl not found. Install: gcloud components install kubectl"
        exit 1
    fi

    # ── Build and push Docker image ────────────────────────────────────────
    print_info "Building MCP Server Docker image for linux/amd64..."
    cd "$ROOT_DIR"
    docker buildx build \
        --platform linux/amd64 \
        -t "$IMAGE_TAG" \
        --load \
        -f mcp-server/Dockerfile \
        .
    print_success "Image built"

    print_info "Pushing image to Artifact Registry..."
    docker push "$IMAGE_TAG"
    print_success "Image pushed"

    # ── Apply K8s manifests ────────────────────────────────────────────────
    print_info "Applying K8s manifests..."

    # Ensure namespace exists
    kubectl create namespace mem-dog --dry-run=client -o yaml | kubectl apply -f -

    # ConfigMap
    kubectl -n mem-dog create configmap mcp-server-config \
        --from-literal=MEM_DOG_API_URL="http://api.mem-dog.svc.cluster.local:8080" \
        --from-literal=LOG_LEVEL="${LOG_LEVEL:-INFO}" \
        --from-literal=PORT="8080" \
        --dry-run=client -o yaml | kubectl apply -f -
    print_success "ConfigMap applied"

    # Deployment
    kubectl apply -f "$ROOT_DIR/k8s/mcp-server-deployment.yaml"
    kubectl -n mem-dog set image deployment/mcp-server mcp-server="$IMAGE_TAG"
    print_success "Deployment applied"

    # Service
    kubectl apply -f "$ROOT_DIR/k8s/mcp-server-service.yaml"
    print_success "Service applied"

    # HTTPRoute
    kubectl apply -f "$ROOT_DIR/k8s/mcp-server-httproute.yaml"
    print_success "HTTPRoute applied"

    # ── Wait for rollout ───────────────────────────────────────────────────
    print_info "Waiting for rollout..."
    kubectl -n mem-dog rollout status deployment/mcp-server --timeout=120s || true

    print_success "MCP Server deployed to GKE!"
    echo ""
    echo "MCP endpoint: http://<gateway-ip>/mcp/sse"
    echo "Health check: http://<gateway-ip>/mcp/../health"
}

# =============================================================================
# Autoscaling (KEDA scale-to-zero)
# =============================================================================

setup_autoscaling() {
    print_header "Setting up KEDA autoscaling (scale-to-zero): $ENVIRONMENT"

    GKE_CLUSTER="${GKE_CLUSTER:-mem-dog-${ENVIRONMENT}}"
    GKE_ZONE="${GKE_ZONE:-${REGION}-a}"

    print_info "Connecting to GKE cluster $GKE_CLUSTER..."
    if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
            --zone "$GKE_ZONE" --project "$PROJECT_ID" 2>/dev/null; then
        if ! gcloud container clusters get-credentials "$GKE_CLUSTER" \
                --region "$REGION" --project "$PROJECT_ID" 2>/dev/null; then
            print_error "GKE cluster $GKE_CLUSTER not found."
            exit 1
        fi
    fi
    print_success "Connected to GKE cluster: $GKE_CLUSTER"

    # Install KEDA if not present
    if ! kubectl get namespace keda &>/dev/null; then
        print_info "Installing KEDA..."
        if command -v helm &>/dev/null; then
            helm repo add kedacore https://kedacore.github.io/charts 2>/dev/null
            helm repo update kedacore
            helm install keda kedacore/keda --namespace keda --create-namespace --wait
        else
            print_info "Helm not found, using kubectl apply..."
            kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.16.1/keda-2.16.1.yaml
            print_info "Waiting for KEDA to be ready..."
            kubectl wait --for=condition=available deployment/keda-operator -n keda --timeout=120s || true
        fi
        print_success "KEDA installed"
    else
        print_success "KEDA already installed"
    fi

    # Apply ScaledObjects
    print_info "Applying ScaledObject manifests..."
    kubectl apply -f "$ROOT_DIR/k8s/autoscaling/ollama-embedding.yaml"
    kubectl apply -f "$ROOT_DIR/k8s/autoscaling/ollama-chat.yaml"
    kubectl apply -f "$ROOT_DIR/k8s/autoscaling/webhook-pipeline.yaml"
    kubectl apply -f "$ROOT_DIR/k8s/autoscaling/api.yaml"
    kubectl apply -f "$ROOT_DIR/k8s/autoscaling/mcp-server.yaml"
    kubectl apply -f "$ROOT_DIR/k8s/autoscaling/webhook-gateway.yaml"
    print_success "All ScaledObjects applied"

    echo ""
    echo "Scale-to-zero is now active. Services will scale down after their cooldown period."
    echo "  Ollama:          10 min idle → 0 replicas"
    echo "  Pipeline/API/MCP: 15 min idle → 0 replicas"
    echo ""
    echo "Manual wake-up:"
    echo "  kubectl scale deployment -n mem-dog api mcp-server --replicas=1"
    echo "  kubectl scale deployment -n webhook-pipeline webhook-agent ollama ollama-chat --replicas=1"
    echo ""
    echo "Remove autoscaling:"
    echo "  kubectl delete -f k8s/autoscaling/"
}

# =============================================================================
# Status
# =============================================================================

show_status() {
    print_header "Deployment Status"
    
    echo "Project: $PROJECT_ID"
    echo "Region:  $REGION"
    echo "Environment: $ENVIRONMENT"
    echo ""

    print_url_dependencies
    
    # API Status (use same API_URL as in URL dependencies: override or project-number or gcloud)
    echo "API Service (mem-dog-api):"
    if gcloud run services describe "mem-dog-api" \
        --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
        if [ -z "$API_URL" ]; then
            API_URL=$(gcloud run services describe "mem-dog-api" \
                --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
        fi
        print_success "Deployed at: $API_URL"
    else
        print_warning "Not deployed"
    fi
    echo ""
    
    # UI Status
    echo "UI Service (mem-dog-ui-${ENVIRONMENT}):"
    if gcloud run services describe "mem-dog-ui-${ENVIRONMENT}" \
        --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
        UI_URL=$(gcloud run services describe "mem-dog-ui-${ENVIRONMENT}" \
            --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
        print_success "Deployed at: $UI_URL"
    else
        print_warning "Not deployed"
    fi
    echo ""
    
    # Store backends (deploy-api)
    echo "Store backends (deploy-api):"
    echo "  USE_POSTGRES_STORAGE=$USE_POSTGRES_STORAGE  (set true to wire Postgres; run setup-postgres first)"
    echo "  USE_REDIS_STORAGE=$USE_REDIS_STORAGE  (set true to wire Redis; run setup-redis first)"
    echo "  USE_SUPABASE_STORAGE=$USE_SUPABASE_STORAGE  (set true to wire Supabase; run setup-supabase first)"
    echo ""

    # Cloud SQL / PostgreSQL
    local INSTANCE_NAME="mem-dog-pg-${ENVIRONMENT}"
    local SECRET_NAME="mem-dog-postgres-url-${ENVIRONMENT}"
    echo "Cloud SQL (PostgreSQL 16 + pgvector):"
    if gcloud sql instances describe "$INSTANCE_NAME" --project="$PROJECT_ID" &>/dev/null; then
        local SQL_STATE
        SQL_STATE=$(gcloud sql instances describe "$INSTANCE_NAME" --project="$PROJECT_ID" \
            --format='value(state)' 2>/dev/null)
        local SQL_IP
        SQL_IP=$(gcloud sql instances describe "$INSTANCE_NAME" --project="$PROJECT_ID" \
            --format='value(ipAddresses[0].ipAddress)' 2>/dev/null)
        print_success "Instance: $INSTANCE_NAME  state=$SQL_STATE  ip=$SQL_IP"
        if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
            print_success "Secret: $SECRET_NAME (POSTGRES_URL stored)"
        else
            print_warning "Secret $SECRET_NAME not found — re-run setup-postgres to store the URL"
        fi
    else
        print_warning "Instance $INSTANCE_NAME not found — run: setup-postgres"
    fi
    echo ""

    # Redis
    local REDIS_INSTANCE="mem-dog-redis-${ENVIRONMENT}"
    local REDIS_SECRET_NAME="mem-dog-redis-url-${ENVIRONMENT}"
    echo "Redis store:"
    if gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        local REDIS_HOST
        REDIS_HOST=$(gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" --project="$PROJECT_ID" --format='value(host)' 2>/dev/null)
        print_success "Memorystore: $REDIS_INSTANCE (host=$REDIS_HOST)"
    fi
    if gcloud secrets describe "$REDIS_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        print_success "Secret: $REDIS_SECRET_NAME (REDIS_URL stored)"
    else
        print_warning "Secret $REDIS_SECRET_NAME not found — run: deploy-redis or REDIS_URL='...' $0 setup-redis -p $PROJECT_ID -e $ENVIRONMENT"
    fi
    echo ""

    # Supabase
    local SUPABASE_URL_SECRET="mem-dog-supabase-url-${ENVIRONMENT}"
    local SUPABASE_KEY_SECRET="mem-dog-supabase-key-${ENVIRONMENT}"
    echo "Supabase store secrets:"
    if gcloud secrets describe "$SUPABASE_URL_SECRET" --project="$PROJECT_ID" &>/dev/null && \
       gcloud secrets describe "$SUPABASE_KEY_SECRET" --project="$PROJECT_ID" &>/dev/null; then
        print_success "Secrets: $SUPABASE_URL_SECRET, $SUPABASE_KEY_SECRET"
    else
        print_warning "Supabase secrets not found — run: SUPABASE_URL='...' SUPABASE_SERVICE_ROLE_KEY='...' $0 setup-supabase -p $PROJECT_ID -e $ENVIRONMENT"
    fi
    echo ""

    # System Config Bucket
    echo "System Config Bucket:"
    SYSCONFIG_BUCKET="${PROJECT_ID}-mem-dog-sysconfig-${ENVIRONMENT}"
    if gcloud storage buckets describe "gs://$SYSCONFIG_BUCKET" &>/dev/null; then
        print_success "$SYSCONFIG_BUCKET"
        if gcloud storage cat "gs://$SYSCONFIG_BUCKET/platform-config.json" &>/dev/null; then
            print_success "  platform-config.json exists"
        else
            print_warning "  platform-config.json not found"
        fi
    else
        print_warning "$SYSCONFIG_BUCKET (not found)"
    fi
    echo ""
    
    # Buckets (Core)
    echo "Core GCS Buckets:"
    for bucket_suffix in raw meta memories users; do
        BUCKET_NAME="${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
        if gcloud storage buckets describe "gs://$BUCKET_NAME" &>/dev/null; then
            print_success "$BUCKET_NAME"
        else
            print_warning "$BUCKET_NAME (not found)"
        fi
    done
    echo ""
    
    # Buckets (AI Layer)
    echo "AI Layer GCS Buckets:"
    for bucket_suffix in prompts embeddings viewpoints aiconfig skills; do
        BUCKET_NAME="${PROJECT_ID}-mem-dog-${bucket_suffix}-${ENVIRONMENT}"
        if gcloud storage buckets describe "gs://$BUCKET_NAME" &>/dev/null; then
            print_success "$BUCKET_NAME"
        else
            print_warning "$BUCKET_NAME (not found)"
        fi
    done
    echo ""

    # AI Chat Model Servers (small / medium / large / very-large tiers)
    echo "AI Chat Model Servers:"
    MODELS_BUCKET="${PROJECT_ID}-mem-dog-models-${ENVIRONMENT}"
    if gcloud storage buckets describe "gs://$MODELS_BUCKET" --project="$PROJECT_ID" &>/dev/null; then
        print_success "Models bucket: $MODELS_BUCKET"
    else
        print_warning "Models bucket: $MODELS_BUCKET (not found — run deploy-model-servers)"
    fi
    for TIER in small medium large very-large; do
        TIER_SVC="mem-dog-model-server-${TIER}-${ENVIRONMENT}"
        if gcloud run services describe "$TIER_SVC" \
            --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
            T_URL=$(gcloud run services describe "$TIER_SVC" \
                --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
            print_success "  Tier $TIER ($TIER_SVC): $T_URL"
        else
            print_warning "  Tier $TIER ($TIER_SVC): not deployed"
        fi
    done
    echo ""

    # Webhook Pipeline
    echo "Webhook Pipeline:"

    TOPIC_NAME="mem-dog-webhook-${ENVIRONMENT}"
    if gcloud pubsub topics describe "$TOPIC_NAME" --project="$PROJECT_ID" &>/dev/null; then
        print_success "Pub/Sub topic: $TOPIC_NAME"
    else
        print_warning "Pub/Sub topic: $TOPIC_NAME (not found)"
    fi

    WEBHOOK_SA_EMAIL="mem-dog-webhook-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    if gcloud iam service-accounts describe "$WEBHOOK_SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        print_success "Service account: $WEBHOOK_SA_EMAIL"
    else
        print_warning "Service account: $WEBHOOK_SA_EMAIL (not found)"
    fi

    RECEIVER_NAME="mem-dog-webhook-receiver-${ENVIRONMENT}"
    if gcloud functions describe "$RECEIVER_NAME" --gen2 --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        RECEIVER_URL=$(gcloud functions describe "$RECEIVER_NAME" \
            --gen2 --region="$REGION" --project="$PROJECT_ID" \
            --format='value(serviceConfig.uri)')
        print_success "Receiver function: $RECEIVER_URL"
    else
        print_warning "Receiver function: $RECEIVER_NAME (not deployed)"
    fi

    PROCESSOR_NAME="mem-dog-webhook-processor-${ENVIRONMENT}"
    if gcloud functions describe "$PROCESSOR_NAME" --gen2 --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        print_success "Processor function: $PROCESSOR_NAME (deployed)"
    else
        print_warning "Processor function: $PROCESSOR_NAME (not deployed)"
    fi

    MODEL_SERVER_NAME="mem-dog-model-server-${ENVIRONMENT}"
    if gcloud run services describe "$MODEL_SERVER_NAME" \
        --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
        MS_URL=$(gcloud run services describe "$MODEL_SERVER_NAME" \
            --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
        print_success "Model server (Cloud Run B): $MS_URL"
    else
        print_warning "Model server: $MODEL_SERVER_NAME (not deployed)"
    fi

    AGENT_SERVICE_NAME="mem-dog-webhook-agent-${ENVIRONMENT}"
    if gcloud run services describe "$AGENT_SERVICE_NAME" \
        --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
        AS_URL=$(gcloud run services describe "$AGENT_SERVICE_NAME" \
            --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
        print_success "ADK agent (Cloud Run A): $AS_URL"
    else
        print_warning "ADK agent: $AGENT_SERVICE_NAME (not deployed)"
    fi

    GATEWAY_NAME="mem-dog-webhook-gw-${ENVIRONMENT}"
    if gcloud api-gateway gateways describe "$GATEWAY_NAME" \
        --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
        GATEWAY_URL=$(gcloud api-gateway gateways describe "$GATEWAY_NAME" \
            --location="$REGION" --project="$PROJECT_ID" \
            --format='value(defaultHostname)')
        print_success "API Gateway: https://$GATEWAY_URL"
    else
        print_warning "API Gateway: $GATEWAY_NAME (not deployed)"
    fi
    echo ""

    # Webhook Gateway (Cloud Run)
    echo "Webhook Gateway (Cloud Run):"
    WGW_SERVICE_NAME="mem-dog-webhook-gateway-${ENVIRONMENT}"
    if gcloud run services describe "$WGW_SERVICE_NAME" \
        --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
        WGW_URL=$(gcloud run services describe "$WGW_SERVICE_NAME" \
            --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
        print_success "Webhook Gateway: $WGW_URL"
        print_success "  Docs:      $WGW_URL/docs"
        print_success "  Webhooks:  $WGW_URL/webhooks/{channel_type}"
        print_success "  Providers: $WGW_URL/providers"
    else
        print_warning "Webhook Gateway: $WGW_SERVICE_NAME (not deployed on Cloud Run)"
        echo "  Deploy: $0 deploy-webhook-gateway -p $PROJECT_ID -e $ENVIRONMENT"
    fi
    echo ""

    # Webhook Gateway (GKE — open-jaws)
    echo "Webhook Gateway (GKE — open-jaws):"
    if command -v kubectl &>/dev/null && kubectl get namespace webhook-gateway &>/dev/null 2>&1; then
        WGW_PODS=$(kubectl get pods -n webhook-gateway -l app=webhook-gateway --no-headers 2>/dev/null | wc -l | tr -d ' ')
        WGW_READY=$(kubectl get pods -n webhook-gateway -l app=webhook-gateway --no-headers 2>/dev/null | grep -c "Running" || echo "0")
        print_success "Pods: $WGW_READY/$WGW_PODS running"
        GW_IP=$(kubectl get gateway open-jaws -n webhook-gateway \
            -o jsonpath='{.status.addresses[0].value}' 2>/dev/null || echo "")
        if [ -n "$GW_IP" ]; then
            print_success "open-jaws Gateway IP: $GW_IP"
            print_success "  Health:    http://$GW_IP/health"
            print_success "  Webhooks:  http://$GW_IP/webhooks/{channel_type}"
            print_success "  Providers: http://$GW_IP/providers"
        else
            print_warning "open-jaws Gateway: IP not yet assigned"
        fi
    else
        print_warning "Webhook Gateway: not deployed on GKE (namespace webhook-gateway not found)"
        echo "  Deploy: $0 deploy-webhook-gateway-gke -p $PROJECT_ID -e $ENVIRONMENT"
    fi
}

# =============================================================================
# GCP VM options (config-driven VM types and models)
# =============================================================================

GCP_VM_OPTIONS_JSON="${SCRIPT_DIR}/gcp-vm-options.json"
MEM_DOG_VM_MODEL_FILE="${SCRIPT_DIR}/.mem-dog-vm-model"

# List VM types from config. Requires jq.
list_vm_options() {
    if [[ ! -f "$GCP_VM_OPTIONS_JSON" ]] || ! command -v jq &>/dev/null; then
        print_error "Cannot list VM options: $GCP_VM_OPTIONS_JSON not found or jq not installed (brew install jq)"
        exit 1
    fi
    echo ""
    echo "VM types from $GCP_VM_OPTIONS_JSON:"
    echo ""
    jq -r '.instances | to_entries[] | "  \(.key + 1). \(.value.instance_type)  (\(.value.gpu), \(.value.gpu_vram_gb)GB, $\(.value.cost_per_hour)/hr)"' "$GCP_VM_OPTIONS_JSON"
    echo ""
    echo "Use: deploy-vm-instance --vm <number> or --vm \"<instance_type>\" (e.g. \"g2-standard-8 + L4\")"
    echo "     deploy-vm-instance --vm 2 --model \"Gemma-3-12B\""
    echo ""
}

# Resolve instance index (0-based) from config. VM_TYPE can be: 1-4, or instance_type string, or legacy g2-standard-8 etc.
# Sets global INSTANCE_INDEX (0-based) and uses config for GCP fields. Returns 0 if config used, 1 if legacy.
resolve_vm_from_config() {
    local VM_TYPE="$1"
    if [[ ! -f "$GCP_VM_OPTIONS_JSON" ]] || ! command -v jq &>/dev/null; then
        return 1
    fi
    # Numeric index (1-based from CLI)
    if [[ "$VM_TYPE" =~ ^[1-9][0-9]*$ ]]; then
        local count
        count=$(jq '.instances | length' "$GCP_VM_OPTIONS_JSON")
        if (( VM_TYPE < 1 || VM_TYPE > count )); then
            print_error "VM type index $VM_TYPE out of range (1-$count)"
            exit 1
        fi
        INSTANCE_INDEX=$((VM_TYPE - 1))
    else
        # Match instance_type (exact or partial)
        INSTANCE_INDEX=$(jq -r --arg t "$VM_TYPE" '
            .instances | to_entries[] | select(.value.instance_type == $t or (.value.instance_type | index($t) != null)) | .key
        ' "$GCP_VM_OPTIONS_JSON" | head -1)
        if [[ -z "$INSTANCE_INDEX" || "$INSTANCE_INDEX" == "null" ]]; then
            # Legacy token not in instance_type string: a2-ultragpu-1g -> config index 3 (A100 80GB)
            if [[ "$VM_TYPE" == "a2-ultragpu-1g" ]]; then
                INSTANCE_INDEX=3
            else
                return 1
            fi
        fi
    fi
    return 0
}

# Get GCP fields for instance at INSTANCE_INDEX. Sets GPU_TYPE, GPU_COUNT, GCP_MACHINE_TYPE, DESCRIPTION.
get_gcp_fields_for_instance() {
    local idx="$1"
    GCP_MACHINE_TYPE=$(jq -r --argjson i "$idx" '.instances[$i].gcp_machine_type' "$GCP_VM_OPTIONS_JSON")
    GPU_TYPE=$(jq -r --argjson i "$idx" '.instances[$i].gcp_accelerator_type' "$GCP_VM_OPTIONS_JSON")
    GPU_COUNT=$(jq -r --argjson i "$idx" '.instances[$i].gcp_accelerator_count' "$GCP_VM_OPTIONS_JSON")
    DESCRIPTION=$(jq -r --argjson i "$idx" '.instances[$i].instance_type' "$GCP_VM_OPTIONS_JSON")
    if [[ -z "$GCP_MACHINE_TYPE" || "$GCP_MACHINE_TYPE" == "null" ]]; then
        print_error "Missing gcp_machine_type for instance index $idx in $GCP_VM_OPTIONS_JSON"
        exit 1
    fi
}

# Get ollama_tag for model name or catalog_model_id in instance at INSTANCE_INDEX. Echo tag or empty.
get_ollama_tag_for_model() {
    local idx="$1"
    local model_name="$2"
    jq -r --argjson i "$idx" --arg m "$model_name" '
        .instances[$i].models[] | select(.model == $m or (.catalog_model_id != null and .catalog_model_id == $m)) | .ollama_tag // empty
    ' "$GCP_VM_OPTIONS_JSON" | head -1
}

# Get first recommended model's ollama_tag for instance at INSTANCE_INDEX.
get_default_ollama_tag_for_instance() {
    local idx="$1"
    jq -r --argjson i "$idx" '
        .instances[$i].models[] | select(.recommended == true) | .ollama_tag
    ' "$GCP_VM_OPTIONS_JSON" | head -1
}

# =============================================================================
# GCP Cloud Run options (config-driven tier CPU/memory for deploy-model-servers)
# =============================================================================

GCP_CLOUDRUN_OPTIONS_JSON="${SCRIPT_DIR}/gcp-cloudrun-options.json"

# List Cloud Run tier config from gcp-cloudrun-options.json (tiers small/medium/large/very-large).
list_cloudrun_options() {
    if [[ ! -f "$GCP_CLOUDRUN_OPTIONS_JSON" ]] || ! command -v jq &>/dev/null; then
        print_error "Cannot list Cloud Run options: $GCP_CLOUDRUN_OPTIONS_JSON not found or jq not installed (brew install jq)"
        exit 1
    fi
    echo ""
    echo "Cloud Run tier config from $GCP_CLOUDRUN_OPTIONS_JSON (used by deploy-model-servers):"
    echo ""
    jq -r '
        .instances[] | select(.tier != null) |
        "  \(.tier): \(.vcpu) vCPU, \(.memory_gb) GB RAM  (instance_type: \(.instance_type))"
    ' "$GCP_CLOUDRUN_OPTIONS_JSON"
    echo ""
    echo "Deploy: ./scripts/manual-deploy.sh deploy-model-servers -p PROJECT -e ENV [small medium large very-large]"
    echo ""
}

# Write tier machine definitions to AI config bucket (machines/tier_machines.json).
# API reads from here so list_machines returns tier machines. Call after deploy-model-servers.
# Usage: write_tier_machines_to_ai_config  (uses TIER_URLS array: "tier=url" entries)
write_tier_machines_to_ai_config() {
    local AI_CONFIG_BUCKET="${PROJECT_ID}-mem-dog-aiconfig-${ENVIRONMENT}"
    if ! gcloud storage buckets describe "gs://$AI_CONFIG_BUCKET" --project="$PROJECT_ID" &>/dev/null; then
        print_warning "AI config bucket $AI_CONFIG_BUCKET not found; skipping tier_machines.json"
        return
    fi
    local tier url memory_gb disp json_tiers=""
    for entry in "${TIER_URLS[@]}"; do
        tier="${entry%%=*}"
        url="${entry#*=}"
        if get_cloudrun_tier_resources "$tier" 2>/dev/null; then
            memory_gb="${CLOUDRUN_MEM%Gi}"
        else
            case "$tier" in
                small)      memory_gb=6 ;;
                medium)     memory_gb=12 ;;
                large)      memory_gb=24 ;;
                very-large) memory_gb=80 ;;
                *)          memory_gb=8 ;;
            esac
        fi
        case "$tier" in
            small)      disp="Small" ;;
            medium)     disp="Medium" ;;
            large)      disp="Large" ;;
            very-large) disp="Very Large" ;;
            *)          disp="$tier" ;;
        esac
        [[ -n "$json_tiers" ]] && json_tiers="$json_tiers,"
        json_tiers="$json_tiers\"$tier\":{\"base_url\":\"$url\",\"memory_gb\":$memory_gb,\"name\":\"Cloud Run – $disp\"}"
    done
    local json="{\"tiers\":{$json_tiers}}"
    echo "$json" | gcloud storage cp - "gs://${AI_CONFIG_BUCKET}/machines/tier_machines.json" \
        --content-type="application/json" \
        --project="$PROJECT_ID"
    print_success "tier_machines.json written to gs://${AI_CONFIG_BUCKET}/machines/"
}

# Read CPU and memory for a tier from config. Sets CLOUDRUN_CPU and CLOUDRUN_MEM (e.g. 2, 6Gi).
# Returns 0 if config found, 1 otherwise.
get_cloudrun_tier_resources() {
    local tier="$1"
    CLOUDRUN_CPU=""
    CLOUDRUN_MEM=""
    if [[ ! -f "$GCP_CLOUDRUN_OPTIONS_JSON" ]] || ! command -v jq &>/dev/null; then
        return 1
    fi
    local vcpu memory_gb
    vcpu=$(jq -r --arg t "$tier" '.instances[] | select(.tier == $t) | .vcpu' "$GCP_CLOUDRUN_OPTIONS_JSON" | head -1)
    memory_gb=$(jq -r --arg t "$tier" '.instances[] | select(.tier == $t) | .memory_gb' "$GCP_CLOUDRUN_OPTIONS_JSON" | head -1)
    if [[ -z "$vcpu" || "$vcpu" == "null" ]] || [[ -z "$memory_gb" || "$memory_gb" == "null" ]]; then
        return 1
    fi
    CLOUDRUN_CPU="$vcpu"
    CLOUDRUN_MEM="${memory_gb}Gi"
    return 0
}

# =============================================================================
# Deploy VM Instance (for vm-instance model category)
# =============================================================================

deploy_vm_instance() {
    local VM_TYPE="${1:-a2-highgpu-1g}"  # Default to A100 for Gemma 3 27B
    local USE_MODEL="${2:-}"             # Optional: model name for this VM (resolved to ollama_tag)
    
    # Config-driven: resolve from gcp-vm-options.json if available
    local use_config=false
    if resolve_vm_from_config "$VM_TYPE"; then
        use_config=true
        get_gcp_fields_for_instance "$INSTANCE_INDEX"
        VM_TYPE="$GCP_MACHINE_TYPE"  # use GCP machine type for VM name and gcloud
    else
        # Legacy: validate and set GPU configuration
        case "$VM_TYPE" in
            g2-standard-8)
                GPU_TYPE="nvidia-l4"
                GPU_COUNT=1
                GCP_MACHINE_TYPE="g2-standard-8"
                DESCRIPTION="NVIDIA L4 GPU (24GB) - 7B-13B models"
                ;;
            g2-standard-24)
                GPU_TYPE="nvidia-l4"
                GPU_COUNT=2
                GCP_MACHINE_TYPE="g2-standard-24"
                DESCRIPTION="NVIDIA L4 GPU (2x24GB) - 13B-30B models"
                ;;
            a2-highgpu-1g)
                GPU_TYPE="nvidia-tesla-a100"
                GPU_COUNT=1
                GCP_MACHINE_TYPE="a2-highgpu-1g"
                DESCRIPTION="NVIDIA A100 GPU (40GB) - 27B-70B models"
                ;;
            a2-ultragpu-1g)
                GPU_TYPE="nvidia-a100-80gb"
                GPU_COUNT=1
                GCP_MACHINE_TYPE="a2-ultragpu-1g"
                DESCRIPTION="NVIDIA A100-80GB GPU - 70B+ models"
                ;;
            *)
                print_error "Invalid VM type: $VM_TYPE"
                print_error "Valid types: g2-standard-8, g2-standard-24, a2-highgpu-1g (default), a2-ultragpu-1g"
                print_error "Or use config: ./scripts/manual-deploy.sh deploy-vm-instance --list-vms -p PROJECT"
                exit 1
                ;;
        esac
    fi
    
    # Resolve optional model to ollama_tag (for downstream setup script)
    OLLAMA_MODEL_TAG=""
    if [[ -n "$USE_MODEL" ]]; then
        if [[ "$use_config" == true ]]; then
            OLLAMA_MODEL_TAG=$(get_ollama_tag_for_model "$INSTANCE_INDEX" "$USE_MODEL")
            if [[ -z "$OLLAMA_MODEL_TAG" ]]; then
                print_warning "Model \"$USE_MODEL\" not found for this VM type in config; use --model <name> from instances[].models[].model"
            fi
        fi
        # If not from config, we could leave OLLAMA_MODEL_TAG empty (setup script will use default)
    fi
    if [[ -z "$OLLAMA_MODEL_TAG" ]]; then
        if [[ "$use_config" == true ]]; then
            OLLAMA_MODEL_TAG=$(get_default_ollama_tag_for_instance "$INSTANCE_INDEX")
        fi
        [[ -z "$OLLAMA_MODEL_TAG" ]] && OLLAMA_MODEL_TAG="gemma3:27b"
    fi
    if [[ -n "$OLLAMA_MODEL_TAG" ]]; then
        echo "$OLLAMA_MODEL_TAG" > "$MEM_DOG_VM_MODEL_FILE"
    fi
    
    print_header "Deploying VM Instance: $VM_TYPE ($DESCRIPTION)"
    
    VM_NAME="mem-dog-vm-${VM_TYPE}-${ENVIRONMENT}"
    ZONE="${REGION}-a"
    
    # Check if VM already exists
    if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
        print_warning "VM $VM_NAME already exists in zone $ZONE"
        EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
            --zone="$ZONE" --project="$PROJECT_ID" \
            --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
        print_info "External IP: $EXTERNAL_IP"
        print_info "To register in mem-dog API, run:"
        echo ""
        echo "curl -X POST \"\$API_URL/api/v1/models/vm-instances\" \\"
        echo "  -H \"Content-Type: application/json\" \\"
        echo "  -d '{\"machine_type\": \"$VM_TYPE\", \"base_url\": \"http://$EXTERNAL_IP:8000\", \"name\": \"${DESCRIPTION}\"}'"
        return
    fi
    
    # Create firewall rule if it doesn't exist
    if ! gcloud compute firewall-rules describe mem-dog-model-server --project="$PROJECT_ID" &>/dev/null; then
        print_info "Creating firewall rule for model server..."
        gcloud compute firewall-rules create mem-dog-model-server \
            --project="$PROJECT_ID" \
            --allow tcp:8000 \
            --source-ranges=0.0.0.0/0 \
            --target-tags=model-server \
            --description="Allow access to model server on port 8000"
        print_success "Firewall rule created"
    else
        print_success "Firewall rule already exists"
    fi
    
    # Create VM instance
    print_info "Creating VM instance $VM_NAME with $DESCRIPTION..."
    gcloud compute instances create "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$ZONE" \
        --machine-type="${GCP_MACHINE_TYPE:-$VM_TYPE}" \
        --accelerator="count=$GPU_COUNT,type=$GPU_TYPE" \
        --image-family=debian-11 \
        --image-project=debian-cloud \
        --boot-disk-size=200GB \
        --boot-disk-type=pd-balanced \
        --metadata=install-nvidia-driver=True \
        --tags=model-server \
        --scopes=cloud-platform \
        --maintenance-policy=TERMINATE
    
    print_success "VM instance created: $VM_NAME"
    
    # Wait for VM to be ready
    print_info "Waiting for VM to be ready (60s)..."
    sleep 60
    
    # Get external IP
    EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
        --zone="$ZONE" --project="$PROJECT_ID" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    
    print_success "VM is ready!"
    echo ""
    print_info "VM Details:"
    echo "  Name: $VM_NAME"
    echo "  Type: $VM_TYPE ($DESCRIPTION)"
    echo "  Zone: $ZONE"
    echo "  External IP: $EXTERNAL_IP"
    echo ""
    
    print_info "Next steps:"
    echo ""
    echo "1. SSH into the VM:"
    echo "   gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
    echo ""
    echo "2. Run the automated setup script (RECOMMENDED):"
    echo "   curl -fsSL https://raw.githubusercontent.com/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\([^.]*\).*/\1/')/main/scripts/setup-vm-ollama.sh | bash"
    echo ""
    echo "   OR copy and run locally:"
    echo "   # From your local machine"
    echo "   gcloud compute scp scripts/setup-vm-ollama.sh $VM_NAME:~ --zone=$ZONE --project=$PROJECT_ID"
    echo "   gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID --command=\"chmod +x setup-vm-ollama.sh && ./setup-vm-ollama.sh\""
    echo ""
    echo "3. After setup completes, download and run a model:"
    echo "   # SSH into VM"
    echo "   gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
    echo "   "
    echo "   # Download model (e.g. ${OLLAMA_MODEL_TAG:-gemma3:27b})"
    echo "   ollama pull ${OLLAMA_MODEL_TAG:-gemma3:27b}"
    echo ""
    echo "4. Register VM in mem-dog API:"
    echo "   curl -X POST \"\$API_URL/api/v1/models/vm-instances\" \\"
    echo "     -H \"Content-Type: application/json\" \\"
    echo "     -d '{\"machine_type\": \"$VM_TYPE\", \"base_url\": \"http://$EXTERNAL_IP:8000\", \"name\": \"${DESCRIPTION}\"}'"
    echo ""
    echo "5. Test the OpenAI-compatible API:"
    echo "   curl http://$EXTERNAL_IP:8000/health"
    echo "   curl http://$EXTERNAL_IP:8000/v1/models"
    echo "   curl -X POST http://$EXTERNAL_IP:8000/v1/chat/completions \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"model\": \"${OLLAMA_MODEL_TAG:-gemma3:27b}\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'"
    echo ""
    print_warning "Cost saving: Stop VM when not in use to avoid charges"
    echo "   gcloud compute instances stop $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
    echo "   gcloud compute instances start $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
    echo ""
}

# =============================================================================
# Parse Arguments
# =============================================================================

COMMAND=""
DEPLOY_MODEL_TIERS=""   # optional: for deploy-model-servers, e.g. "very-large" or "small medium"
VM_INSTANCE_TYPE=""     # optional: for deploy-vm-instance (index 1-N, instance_type label, or legacy type)
VM_INSTANCE_MODEL=""    # optional: for deploy-vm-instance, model name from config (resolved to ollama_tag)
LIST_VMS=""
LIST_CLOUDRUN=""
CONFIRM=""              # required for destroy-postgres
KEEP_BUCKETS=""         # optional for destroy.sh: do not delete GCS buckets
KEEP_INSTANCE=""        # optional for destroy-postgres: do not delete Cloud SQL instance

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -e|--env)
            ENVIRONMENT="$2"
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
        --keep-instance)
            KEEP_INSTANCE=1
            shift
            ;;
        --delete-secrets)
            DELETE_SECRETS=1
            shift
            ;;
        -h|--help)
            show_help
            ;;
        --list-vms)
            LIST_VMS=1
            shift
            ;;
        --list-cloudrun)
            LIST_CLOUDRUN=1
            shift
            ;;
        --vm)
            VM_INSTANCE_TYPE="$2"
            shift 2
            ;;
        --model)
            VM_INSTANCE_MODEL="$2"
            shift 2
            ;;
        setup-env|setup-postgres|destroy-postgres|setup-redis|setup-supabase|deploy-redis|deploy-api|deploy-ui|deploy-ui-read|deploy-api-docs|deploy-all|deploy-model-servers|deploy-vm-instance|setup-webhook|deploy-model-server|deploy-agent|deploy-webhook|deploy-webhook-gateway|deploy-webhook-gateway-gke|deploy-openclaw-node-gke|deploy-supabase-gke|redeploy-supabase-gke|seed-supabase-gke|destroy-supabase-data-gke|destroy-supabase-gke|deploy-api-gke|deploy-webhook-pipeline-gke|deploy-mcp-server-gke|setup-autoscaling|restart-gke|status)
            COMMAND="$1"
            shift
            ;;
        small|medium|large|very-large)
            if [ "$COMMAND" = "deploy-model-servers" ]; then
                DEPLOY_MODEL_TIERS="${DEPLOY_MODEL_TIERS:+$DEPLOY_MODEL_TIERS }$1"
                shift
            else
                print_error "Unknown option: $1"
                show_help
            fi
            ;;
        g2-standard-8|g2-standard-24|a2-highgpu-1g|a2-ultragpu-1g)
            if [ "$COMMAND" = "deploy-vm-instance" ] && [ -z "$VM_INSTANCE_TYPE" ]; then
                VM_INSTANCE_TYPE="$1"
                shift
            else
                print_error "Unknown option: $1"
                show_help
            fi
            ;;
        *)
            if [ "$COMMAND" = "deploy-vm-instance" ] && [ -z "$VM_INSTANCE_TYPE" ] && [[ "$1" != -* ]]; then
                VM_INSTANCE_TYPE="$1"
                shift
            else
                print_error "Unknown option: $1"
                show_help
            fi
            ;;
    esac
done

# =============================================================================
# Main
# =============================================================================

if [ -z "$COMMAND" ]; then
    print_error "No command specified"
    show_help
fi

# --list-vms: list VM options from config and exit (no project required)
if [ "$COMMAND" = "deploy-vm-instance" ] && [ -n "$LIST_VMS" ]; then
    list_vm_options
    exit 0
fi

# --list-cloudrun: list Cloud Run tier config from config and exit (no project required)
if [ "$COMMAND" = "deploy-model-servers" ] && [ -n "$LIST_CLOUDRUN" ]; then
    list_cloudrun_options
    exit 0
fi

check_prerequisites

# During deploy commands, show URL dependencies so operators see current env/URL state.
case $COMMAND in
    deploy-api|deploy-ui|deploy-api-docs|deploy-all|deploy-model-servers|deploy-model-server|deploy-agent|deploy-webhook|deploy-webhook-gateway|deploy-webhook-gateway-gke|deploy-supabase-gke|redeploy-supabase-gke)
        print_url_dependencies
        ;;
esac

case $COMMAND in
    setup-env)
        setup_env
        ;;
    setup-postgres)
        setup_postgres
        ;;
    destroy-postgres)
        destroy_postgres
        ;;
    setup-redis)
        setup_redis
        ;;
    deploy-redis)
        deploy_redis
        ;;
    setup-supabase)
        setup_supabase
        ;;
    deploy-api)
        deploy_api
        ;;
    deploy-ui)
        deploy_ui
        ;;
    deploy-ui-read)
        UI_READ_ONLY=true deploy_ui
        ;;
    deploy-api-docs)
        deploy_api_docs
        ;;
    deploy-all)
        deploy_all
        ;;
    deploy-model-servers)
        deploy_model_servers
        ;;
    deploy-vm-instance)
        deploy_vm_instance "$VM_INSTANCE_TYPE" "$VM_INSTANCE_MODEL"
        ;;
    setup-webhook)
        setup_webhook
        ;;
    deploy-model-server)
        deploy_model_server
        ;;
    deploy-agent)
        deploy_agent
        ;;
    deploy-webhook)
        deploy_webhook
        ;;
    deploy-webhook-gateway)
        deploy_webhook_gateway
        ;;
    deploy-webhook-gateway-gke)
        deploy_webhook_gateway_gke
        ;;
    deploy-openclaw-node-gke)
        deploy_openclaw_node_gke
        ;;
    deploy-supabase-gke)
        deploy_supabase_gke
        ;;
    redeploy-supabase-gke)
        redeploy_supabase_gke
        ;;
    seed-supabase-gke)
        seed_supabase_gke
        ;;
    destroy-supabase-data-gke)
        destroy_supabase_data_gke
        ;;
    destroy-supabase-gke)
        destroy_supabase_gke
        ;;
    deploy-api-gke)
        deploy_api_gke
        ;;
    deploy-webhook-pipeline-gke)
        deploy_webhook_pipeline_gke
        ;;
    deploy-mcp-server-gke)
        deploy_mcp_server_gke
        ;;
    setup-autoscaling)
        setup_autoscaling
        ;;
    restart-gke)
        restart_gke
        ;;
    status)
        show_status
        ;;
esac
