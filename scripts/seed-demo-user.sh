#!/bin/bash
set -e

# =============================================================================
# Seed Demo User Script for mem-dog
# =============================================================================
# Creates the default "demo" user in the users bucket with all required files:
#   - users/{user_id}/profile.json
#   - users/{user_id}/credentials.json
#   - index/username/demo.json
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - You have access to the GCP project and users bucket
#
# Usage:
#   ./scripts/seed-demo-user.sh [options]
#
# Options:
#   -p, --project    GCP Project ID (required)
#   -e, --env        Environment: dev, staging, production (default: dev)
#   -h, --help       Show this help message
#
# Examples:
#   ./scripts/seed-demo-user.sh -p memdog-dev
#   ./scripts/seed-demo-user.sh -p memdog-dev -e staging
# =============================================================================

# Default values
ENVIRONMENT="dev"
PROJECT_ID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

show_help() {
    head -30 "$0" | tail -25
    exit 0
}

# =============================================================================
# Parse Arguments
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            ;;
    esac
done

# =============================================================================
# Validate
# =============================================================================

if [ -z "$PROJECT_ID" ]; then
    print_error "Project ID is required. Use -p or --project"
    echo ""
    echo "Usage: ./scripts/seed-demo-user.sh -p <project-id> [-e <environment>]"
    exit 1
fi

USERS_BUCKET="${PROJECT_ID}-mem-dog-users-${ENVIRONMENT}"

# Check bucket exists
if ! gcloud storage buckets describe "gs://${USERS_BUCKET}" &>/dev/null; then
    print_error "Users bucket not found: ${USERS_BUCKET}"
    echo "Run setup-env first: ./scripts/manual-deploy.sh setup-env -p ${PROJECT_ID} -e ${ENVIRONMENT}"
    exit 1
fi

# =============================================================================
# Seed Demo User
# =============================================================================

print_header "Seeding Demo User"

USER_ID="00000000-0000-0000-0000-000000000001"
USERNAME="demo"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Project:     ${PROJECT_ID}"
echo "Environment: ${ENVIRONMENT}"
echo "Bucket:      ${USERS_BUCKET}"
echo "User ID:     ${USER_ID}"
echo "Username:    ${USERNAME}"
echo ""

# Check if demo user already exists
if gcloud storage cat "gs://${USERS_BUCKET}/index/username/${USERNAME}.json" &>/dev/null; then
    print_warning "Demo user already exists in bucket"
    echo ""
    echo "Existing profile:"
    EXISTING_USER_ID=$(gcloud storage cat "gs://${USERS_BUCKET}/index/username/${USERNAME}.json" 2>/dev/null | uv run python3 -c "import sys,json; print(json.load(sys.stdin)['user_id'])" 2>/dev/null || echo "unknown")
    gcloud storage cat "gs://${USERS_BUCKET}/users/${EXISTING_USER_ID}/profile.json" 2>/dev/null || echo "(could not read profile)"
    echo ""
    read -p "Overwrite? (y/N): " CONFIRM
    if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
        echo "Aborted."
        exit 0
    fi
    echo ""
fi

# 1. Upload profile.json
print_info "Creating profile.json..."
cat <<EOF | gcloud storage cp - "gs://${USERS_BUCKET}/users/${USER_ID}/profile.json" --content-type="application/json"
{
  "user_id": "${USER_ID}",
  "username": "${USERNAME}",
  "email": "demo@memdog.dev",
  "display_name": "Demo User",
  "role": "user",
  "status": "active",
  "metadata": {},
  "data_count": 0,
  "storage_used_bytes": 0,
  "created_at": "${NOW}",
  "updated_at": "${NOW}",
  "last_active_at": "${NOW}"
}
EOF
print_success "Profile created: users/${USER_ID}/profile.json"

# 2. Upload credentials.json
print_info "Creating credentials.json..."
cat <<EOF | gcloud storage cp - "gs://${USERS_BUCKET}/users/${USER_ID}/credentials.json" --content-type="application/json"
{
  "user_id": "${USER_ID}",
  "password_hash": null,
  "api_keys": [],
  "created_at": "${NOW}",
  "updated_at": "${NOW}"
}
EOF
print_success "Credentials created: users/${USER_ID}/credentials.json"

# 3. Upload username index
print_info "Creating username index..."
cat <<EOF | gcloud storage cp - "gs://${USERS_BUCKET}/index/username/${USERNAME}.json" --content-type="application/json"
{
  "user_id": "${USER_ID}"
}
EOF
print_success "Index created: index/username/${USERNAME}.json"

# =============================================================================
# Verify
# =============================================================================

print_header "Verification"

print_info "Files in users bucket:"
gcloud storage ls "gs://${USERS_BUCKET}/**" 2>/dev/null || print_warning "Could not list bucket contents"

echo ""
print_info "Reading back profile:"
gcloud storage cat "gs://${USERS_BUCKET}/users/${USER_ID}/profile.json" 2>/dev/null || print_warning "Could not read profile"

echo ""

# Test via API if available
API_SERVICE="mem-dog-api"
API_URL=$(gcloud run services describe "${API_SERVICE}" \
    --region us-central1 \
    --project "${PROJECT_ID}" \
    --format 'value(status.url)' 2>/dev/null || echo "")

if [ -n "$API_URL" ]; then
    echo ""
    print_info "Testing via API: ${API_URL}/api/v1/users/username/demo"
    HTTP_CODE=$(curl -s -o /tmp/seed-demo-response.json -w "%{http_code}" "${API_URL}/api/v1/users/username/demo" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        print_success "API returned 200 OK"
        cat /tmp/seed-demo-response.json | uv run python3 -m json.tool 2>/dev/null || cat /tmp/seed-demo-response.json
    else
        print_warning "API returned HTTP ${HTTP_CODE} (API may need redeployment to pick up USER_BUCKET config)"
        cat /tmp/seed-demo-response.json 2>/dev/null
    fi
    rm -f /tmp/seed-demo-response.json
else
    print_warning "API service not found — skipping API verification"
fi

echo ""
print_success "Demo user seeded successfully!"
echo ""
echo "  Username:  demo"
echo "  User ID:   ${USER_ID}"
echo "  Bucket:    ${USERS_BUCKET}"
echo ""
