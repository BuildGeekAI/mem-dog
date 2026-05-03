#!/usr/bin/env bash
# drop-all-data.sh — wipe all data from GCS buckets and/or Supabase tables.
#
# GCS buckets wiped (USER_BUCKET is intentionally skipped):
#   RAW_BUCKET, META_BUCKET, MEMORIES_BUCKET, INDEX_BUCKET, PROMPTS_BUCKET,
#   EMBEDDINGS_BUCKET, VIEWPOINTS_BUCKET, AI_CONFIG_BUCKET, SKILLS_BUCKET,
#   STATS_BUCKET, CHANNELS_BUCKET
#
# Supabase (when STORAGE_BACKEND=supabase or --supabase flag):
#   mem_dog_blobs  — all rows except store_name='users'
#   mem_dog_embeddings — all rows (TRUNCATE)
#
# Usage:
#   ./scripts/drop-all-data.sh -p PROJECT -e ENV [--dry-run] [--yes]
#   ./scripts/drop-all-data.sh -p PROJECT -e ENV --supabase [--dry-run] [--yes]
#
# Examples:
#   ./scripts/drop-all-data.sh -p my-project -e dev --dry-run   # preview
#   ./scripts/drop-all-data.sh -p my-project -e dev --yes       # delete without prompt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENVIRONMENT="${ENVIRONMENT:-dev}"
DRY_RUN=false
YES=false
GCP_PROJECT="${GCP_PROJECT_ID:-}"
# Auto-detect Supabase backend from env; can also be forced with --supabase flag.
STORAGE_BACKEND="${STORAGE_BACKEND:-gcs}"
DO_SUPABASE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--env)       ENVIRONMENT="$2"; shift 2 ;;
    -p|--project)   GCP_PROJECT="$2"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --yes|-y)       YES=true; shift ;;
    --supabase)     DO_SUPABASE=true; shift ;;
    -h|--help)
      head -25 "$0" | grep '^#' | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Auto-enable Supabase wipe when storage backend is supabase.
if [[ "$STORAGE_BACKEND" == "supabase" ]]; then
  DO_SUPABASE=true
fi

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

RAW_BUCKET="${RAW_BUCKET:-$(resolve_bucket RAW_BUCKET raw)}"
META_BUCKET="${META_BUCKET:-$(resolve_bucket META_BUCKET meta)}"
MEMORIES_BUCKET="${MEMORIES_BUCKET:-$(resolve_bucket MEMORIES_BUCKET memories)}"
INDEX_BUCKET="${INDEX_BUCKET:-$(resolve_bucket INDEX_BUCKET index)}"
PROMPTS_BUCKET="${PROMPTS_BUCKET:-$(resolve_bucket PROMPTS_BUCKET prompts)}"
EMBEDDINGS_BUCKET="${EMBEDDINGS_BUCKET:-$(resolve_bucket EMBEDDINGS_BUCKET embeddings)}"
VIEWPOINTS_BUCKET="${VIEWPOINTS_BUCKET:-$(resolve_bucket VIEWPOINTS_BUCKET viewpoints)}"
AI_CONFIG_BUCKET="${AI_CONFIG_BUCKET:-$(resolve_bucket AI_CONFIG_BUCKET ai-config)}"
SKILLS_BUCKET="${SKILLS_BUCKET:-$(resolve_bucket SKILLS_BUCKET skills)}"
STATS_BUCKET="${STATS_BUCKET:-$(resolve_bucket STATS_BUCKET stats)}"
CHANNELS_BUCKET="${CHANNELS_BUCKET:-$(resolve_bucket CHANNELS_BUCKET channels)}"
# USER_BUCKET is intentionally excluded.

if [[ -z "$RAW_BUCKET" && -z "$META_BUCKET" && "$DO_SUPABASE" == "false" ]]; then
  echo "Error: Pass -p PROJECT_ID or set GCP_PROJECT_ID / RAW_BUCKET env vars." >&2
  exit 1
fi

echo "=== memdog drop-all-data ==="
echo "Environment    : ${ENVIRONMENT}"
echo "Project        : ${GCP_PROJECT:-<from gcloud config>}"
echo "Dry run        : ${DRY_RUN}"
echo "Storage backend: ${STORAGE_BACKEND}"
echo ""

# ---------------------------------------------------------------------------
# GCS buckets
# ---------------------------------------------------------------------------

GCS_BUCKETS=(
  "$RAW_BUCKET"
  "$META_BUCKET"
  "$MEMORIES_BUCKET"
  "$INDEX_BUCKET"
  "$PROMPTS_BUCKET"
  "$EMBEDDINGS_BUCKET"
  "$VIEWPOINTS_BUCKET"
  "$AI_CONFIG_BUCKET"
  "$SKILLS_BUCKET"
  "$STATS_BUCKET"
  "$CHANNELS_BUCKET"
)
GCS_LABELS=(
  "raw"
  "meta"
  "memories"
  "index"
  "prompts"
  "embeddings"
  "viewpoints"
  "ai_config"
  "skills"
  "stats"
  "channels"
)

echo "GCS buckets to wipe (USER_BUCKET excluded):"
for i in "${!GCS_BUCKETS[@]}"; do
  b="${GCS_BUCKETS[$i]}"
  label="${GCS_LABELS[$i]}"
  if [[ -z "$b" ]]; then
    echo "  ${label}: [SKIPPED — not configured]"
  else
    echo "  ${label}: gs://${b}"
  fi
done

# ---------------------------------------------------------------------------
# Supabase tables
# ---------------------------------------------------------------------------

if [[ "$DO_SUPABASE" == "true" ]]; then
  echo ""
  echo "Supabase tables to wipe (users store excluded):"
  echo "  mem_dog_blobs      — DELETE WHERE store_name != 'users'"
  echo "  mem_dog_embeddings — TRUNCATE"
fi

echo ""
if [[ "$DRY_RUN" == "false" && "$YES" == "false" ]]; then
  read -r -p "Type 'yes' to confirm deletion of all data above: " confirm
  if [[ "$confirm" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# ---------------------------------------------------------------------------
# Wipe GCS buckets
# ---------------------------------------------------------------------------

wipe_bucket() {
  local bucket="$1"
  local label="$2"
  [[ -z "$bucket" ]] && return
  echo ""
  echo "--- Wiping gs://${bucket} (${label}) ---"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would run: gsutil -m rm -r gs://${bucket}/**"
    gsutil ls -l "gs://${bucket}/**" 2>/dev/null | tail -1 || echo "(bucket empty or does not exist)"
    return
  fi
  if ! gsutil ls "gs://${bucket}" &>/dev/null; then
    echo "Bucket gs://${bucket} does not exist or is not accessible — skipping."
    return
  fi
  gsutil -m rm -r "gs://${bucket}/**" 2>/dev/null || echo "(nothing to delete)"
  echo "Done: gs://${bucket}"
}

for i in "${!GCS_BUCKETS[@]}"; do
  wipe_bucket "${GCS_BUCKETS[$i]}" "${GCS_LABELS[$i]}"
done

# ---------------------------------------------------------------------------
# Wipe Supabase tables
# ---------------------------------------------------------------------------

if [[ "$DO_SUPABASE" == "true" ]]; then
  echo ""
  echo "--- Wiping Supabase tables ---"

  _supa_psql() {
    kubectl exec -i -n supabase supabase-supabase-db-0 -c supabase-db -- \
      psql -U postgres -d postgres "$@"
  }

  if ! _supa_psql -c "SELECT 1;" &>/dev/null; then
    echo "WARNING: Cannot reach Supabase DB pod — skipping Supabase wipe."
    echo "  Ensure kubectl is configured for the right cluster and Supabase is running."
    echo "  To wipe manually:"
    echo "    kubectl exec -i -n supabase supabase-supabase-db-0 -c supabase-db -- \\"
    echo "      psql -U postgres -d postgres -c \"DELETE FROM mem_dog_blobs WHERE store_name != 'users';\""
    echo "    kubectl exec -i -n supabase supabase-supabase-db-0 -c supabase-db -- \\"
    echo "      psql -U postgres -d postgres -c \"TRUNCATE mem_dog_embeddings;\""
  else
    if [[ "$DRY_RUN" == "true" ]]; then
      BLOBS_COUNT=$(_supa_psql -t -A -c "SELECT COUNT(*) FROM mem_dog_blobs WHERE store_name != 'users';" 2>/dev/null | tr -d '[:space:]' || echo "?")
      EMB_COUNT=$(_supa_psql -t -A -c "SELECT COUNT(*) FROM mem_dog_embeddings;" 2>/dev/null | tr -d '[:space:]' || echo "?")
      echo "[DRY RUN] Would delete ${BLOBS_COUNT} rows from mem_dog_blobs (store_name != 'users')"
      echo "[DRY RUN] Would delete ${EMB_COUNT} rows from mem_dog_embeddings"
    else
      _supa_psql -c "DELETE FROM mem_dog_blobs WHERE store_name != 'users';" &>/dev/null \
        && echo "Done: mem_dog_blobs (users store preserved)" \
        || echo "WARNING: mem_dog_blobs delete failed"
      _supa_psql -c "TRUNCATE mem_dog_embeddings;" &>/dev/null \
        && echo "Done: mem_dog_embeddings" \
        || echo "WARNING: mem_dog_embeddings truncate failed"
    fi
  fi
fi

# ---------------------------------------------------------------------------

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry run complete. Re-run without --dry-run to perform actual deletion."
else
  echo "Done. All data wiped (USER_BUCKET / users store preserved)."
fi
