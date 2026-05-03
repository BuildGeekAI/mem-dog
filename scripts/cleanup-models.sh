#!/bin/bash
set -e

# =============================================================================
# Clean Up Models Bucket
# =============================================================================
# This script deletes all objects in the models bucket to allow starting from scratch.
#
# Usage:
#   ./scripts/cleanup-models.sh -p <project-id> [-e <environment>]
# =============================================================================

# Default values
ENVIRONMENT="dev"
PROJECT_ID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Parse arguments
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
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$PROJECT_ID" ]; then
    print_error "Project ID is required. Use -p or --project"
    exit 1
fi

MODELS_BUCKET="${PROJECT_ID}-memdog-models-${ENVIRONMENT}"
BUCKET_URI="gs://${MODELS_BUCKET}"

print_info "Checking if bucket exists: ${BUCKET_URI}"

if ! gcloud storage buckets describe "${BUCKET_URI}" --project="${PROJECT_ID}" &>/dev/null; then
    print_error "Bucket ${BUCKET_URI} does not exist."
    exit 1
fi

print_info "Deleting all objects in ${BUCKET_URI}..."

# List and delete objects
# Using 'gcloud storage rm -r' to remove all objects.
# The bucket itself will NOT be deleted, only its contents.

if gcloud storage rm -r "${BUCKET_URI}/**" --project="${PROJECT_ID}" --quiet; then
    print_success "All objects deleted from ${BUCKET_URI}"
else
    print_error "Failed to delete objects. Bucket might already be empty or permission denied."
fi

print_success "Cleanup complete."
