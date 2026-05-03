#!/bin/bash
set -e

# =============================================================================
# Warmup Script for Mem-Dog Model Servers
# =============================================================================
# Triggers health checks and a minimal inference request for each tier
# to ensure models are loaded and ready in memory.
#
# Usage:
#   ./scripts/warmup-models.sh -p PROJECT_ID [-e ENV] [-r REGION]
# =============================================================================

# Default values
REGION="us-central1"
ENVIRONMENT="dev"
PROJECT_ID=""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Parse args
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
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 -p PROJECT_ID [-e dev] [-r us-central1]"
            exit 1
            ;;
    esac
done

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: Project ID is required (-p)${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Warming up Model Servers${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo ""

# Get API URL
echo -e "${BLUE}ℹ️  Getting API URL...${NC}"
API_URL=$(gcloud run services describe "memdog-api" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format 'value(status.url)' 2>/dev/null || echo "")

if [ -z "$API_URL" ]; then
    echo -e "${RED}❌ API service 'memdog-api' not found.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ API URL: $API_URL${NC}"
echo ""

# Function to warm up a tier
warmup_tier() {
    local tier=$1
    echo -e "${BLUE}--- Tier: $tier ---${NC}"
    
    # 1. Health Check
    echo -n "Checking health... "
    HEALTH_RESP=$(curl -s --max-time 10 "$API_URL/api/v1/ai/query/model-server/health?tier=$tier")
    
    # Check if status is "ok"
    if echo "$HEALTH_RESP" | grep -q '"status":"ok"'; then
        echo -e "${GREEN}OK${NC}"
        
        # 2. Inference Warmup
        echo -n "Running inference warmup (1 token)... "
        start_time=$(date +%s%N)
        
        INFERENCE_RESP=$(curl -s -X POST "$API_URL/api/v1/ai/query/chat" \
            -H "Content-Type: application/json" \
            -d "{
                \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}],
                \"model_tier\": \"$tier\",
                \"max_tokens\": 1,
                \"temperature\": 0.0
            }")
            
        end_time=$(date +%s%N)
        duration=$(( (end_time - start_time) / 1000000 ))
        
        # Check for successful response (response field exists)
        if echo "$INFERENCE_RESP" | grep -q '"response"'; then
            echo -e "${GREEN}Success (${duration}ms)${NC}"
        else
            echo -e "${RED}Failed${NC}"
            echo "Response: $INFERENCE_RESP"
        fi
        
    elif echo "$HEALTH_RESP" | grep -q '"status":"not_configured"'; then
        echo -e "${YELLOW}Not Configured (Skipping)${NC}"
    elif echo "$HEALTH_RESP" | grep -q '"status":"unavailable"'; then
        echo -e "${RED}Unavailable${NC}"
    else
        echo -e "${RED}Error${NC}"
        echo "Response: $HEALTH_RESP"
    fi
    echo ""
}

# Warm up all tiers
for tier in small medium large very-large; do
    warmup_tier "$tier"
done

echo -e "${GREEN}Warmup sequence complete.${NC}"
