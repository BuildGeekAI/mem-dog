#!/bin/bash
# Sync Ollama models to/from GCS bucket
# Usage:
#   ./sync-ollama-models.sh upload   # Save models to GCS
#   ./sync-ollama-models.sh download # Restore models from GCS

set -e

ACTION=$1
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
ENVIRONMENT=${ENVIRONMENT:-dev}
MODELS_BUCKET="${PROJECT_ID}-mem-dog-models-${ENVIRONMENT}"
GCS_PATH="gs://${MODELS_BUCKET}/ollama-models/"
LOCAL_PATH="/var/lib/ollama"

if [[ "$ACTION" == "upload" ]]; then
    echo "📤 Uploading Ollama models to $GCS_PATH..."
    sudo gcloud storage rsync -r "$LOCAL_PATH" "$GCS_PATH" --delete-unmatched-destination-objects=false
    echo "✅ Upload complete"
    
elif [[ "$ACTION" == "download" ]]; then
    echo "📥 Downloading Ollama models from $GCS_PATH..."
    sudo mkdir -p "$LOCAL_PATH"
    sudo gcloud storage rsync -r "$GCS_PATH" "$LOCAL_PATH"
    echo "✅ Download complete"
    
else
    echo "Usage: $0 {upload|download}"
    echo "  upload   - Save /var/lib/ollama to GCS"
    echo "  download - Restore /var/lib/ollama from GCS"
    exit 1
fi
