#!/usr/bin/env bash
# wipe-user-data.sh — delete user-generated data from GCS buckets.
#
# Deletes content from:
#   META_BUCKET, EMBEDDINGS_BUCKET, VIEWPOINTS_BUCKET, USER_BUCKET, MEMORIES_BUCKET
#
# Leaves intact:
#   RAW_BUCKET, GCS_MODELS_BUCKET  (raw blobs and model GGUF files are kept)
#
# Typical use: fresh-start before the Postgres migration, or resetting a
# staging environment without losing raw uploads and model weights.
#
# Usage:
#   ./scripts/wipe-user-data.sh [--env ENV] [--dry-run]
#
# Examples:
#   ./scripts/wipe-user-data.sh --env staging --dry-run   # preview what will be deleted
#   ./scripts/wipe-user-data.sh --env production          # actually delete

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ─── Defaults ───────────────────────────────────────────────────────────────
ENVIRONMENT="${ENVIRONMENT:-development}"
DRY_RUN=false
GCP_PROJECT="${GCP_PROJECT_ID:-}"

# ─── Argument parsing ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)      ENVIRONMENT="$2"; shift 2 ;;
    --project)  GCP_PROJECT="$2"; shift 2 ;;
    --dry-run)  DRY_RUN=true; shift ;;
    -h|--help)
      grep '^# ' "$0" | sed 's/^# //'
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

echo "=== memdog wipe-user-data ==="
echo "Environment : ${ENVIRONMENT}"
echo "Project     : ${GCP_PROJECT:-<from gcloud config>}"
echo "Dry run     : ${DRY_RUN}"
echo ""

# ─── Load system config to resolve bucket names ──────────────────────────────
# Prefer env vars; fall back to naming convention: {project}-memdog-{store}-{env}
resolve_bucket() {
  local env_var="$1"
  local store_name="$2"
  local value="${!env_var:-}"
  if [[ -n "$value" ]]; then
    echo "$value"
  elif [[ -n "$GCP_PROJECT" ]]; then
    echo "${GCP_PROJECT}-memdog-${store_name}-${ENVIRONMENT}"
  else
    echo ""
  fi
}

META_BUCKET="${META_BUCKET:-$(resolve_bucket META_BUCKET meta)}"
EMBEDDINGS_BUCKET="${EMBEDDINGS_BUCKET:-$(resolve_bucket EMBEDDINGS_BUCKET embeddings)}"
VIEWPOINTS_BUCKET="${VIEWPOINTS_BUCKET:-$(resolve_bucket VIEWPOINTS_BUCKET viewpoints)}"
USER_BUCKET="${USER_BUCKET:-$(resolve_bucket USER_BUCKET users)}"
MEMORIES_BUCKET="${MEMORIES_BUCKET:-$(resolve_bucket MEMORIES_BUCKET memories)}"

BUCKETS=(
  "$META_BUCKET"
  "$EMBEDDINGS_BUCKET"
  "$VIEWPOINTS_BUCKET"
  "$USER_BUCKET"
  "$MEMORIES_BUCKET"
)

# ─── Safety check ────────────────────────────────────────────────────────────
echo "Buckets that will be wiped:"
for b in "${BUCKETS[@]}"; do
  if [[ -z "$b" ]]; then
    echo "  [SKIPPED — not configured]"
  else
    echo "  gs://${b}"
  fi
done
echo ""

if [[ "$DRY_RUN" == "false" ]]; then
  read -r -p "Type 'yes' to confirm deletion of all objects in the buckets above: " confirm
  if [[ "$confirm" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# ─── Delete function ─────────────────────────────────────────────────────────
wipe_bucket() {
  local bucket="$1"
  if [[ -z "$bucket" ]]; then
    return
  fi

  echo ""
  echo "--- Wiping gs://${bucket} ---"

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would run: gsutil -m rm -r gs://${bucket}/**"
    # Show object count instead
    gsutil ls -l "gs://${bucket}/**" 2>/dev/null | tail -1 || echo "(bucket empty or does not exist)"
    return
  fi

  # Check the bucket exists first
  if ! gsutil ls "gs://${bucket}" &>/dev/null; then
    echo "Bucket gs://${bucket} does not exist or is not accessible — skipping."
    return
  fi

  # Delete all objects (not the bucket itself)
  gsutil -m rm -r "gs://${bucket}/**" 2>/dev/null || echo "(nothing to delete)"
  echo "Done: gs://${bucket}"
}

# ─── Run ─────────────────────────────────────────────────────────────────────
for bucket in "${BUCKETS[@]}"; do
  wipe_bucket "$bucket"
done

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry run complete. Re-run without --dry-run to perform actual deletion."
else
  echo "User data wiped. RAW_BUCKET and GCS_MODELS_BUCKET are untouched."
  echo ""
  echo "Next steps:"
  echo "  1. Apply the Postgres schema:  cd api && alembic upgrade head"
  echo "  2. Deploy the updated API:     ./scripts/manual-deploy.sh deploy-api"
fi
