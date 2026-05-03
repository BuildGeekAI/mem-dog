#!/usr/bin/env bash
# remove-postgres-dependencies.sh — Remove all Postgres-related code and dependencies.
#
# The API uses GCS/local blob storage only; Postgres is deprecated. This script:
#   - Deletes api/app/postgres_store.py and api/alembic/
#   - Removes sqlalchemy, psycopg2-binary, pgvector, alembic from api/requirements.txt
#   - Deletes postgres-only scripts (fix-postgres-permissions, cleanup-postgres-migrated-buckets, migrate-model-status-to-postgres)
#   - Updates docstrings/comments that reference Postgres
#   - Optionally patches scripts/manual-deploy.sh to remove setup-postgres and POSTGRES_URL wiring
#
# Uses uv for the API venv: ensures uv is available and runs post-apply steps (sync, tests) with uv.
#
# Usage:
#   ./scripts/remove-postgres-dependencies.sh           # Dry run (print what would be done)
#   ./scripts/remove-postgres-dependencies.sh --apply  # Apply changes
#
# Full manual steps after running: docs/setup/postgres-removal-manual-steps.md
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
API_DIR="$ROOT_DIR/api"
APPLY=false
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=true
fi

# Use uv's base venv for the API: ensure uv is available and we're in the project root.
check_uv() {
  if ! command -v uv &>/dev/null; then
    echo "uv is not installed or not in PATH. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi
}

action() {
  if $APPLY; then
    "$@"
  else
    echo "[DRY RUN] would run: $*"
  fi
}

delete_file() {
  if [[ -f "$1" ]]; then
    action rm -f "$1"
    echo "  - delete $1"
  else
    echo "  - skip (missing) $1"
  fi
}

delete_dir() {
  if [[ -d "$1" ]]; then
    action rm -rf "$1"
    echo "  - delete directory $1"
  else
    echo "  - skip (missing) $1"
  fi
}

check_uv
echo "=== Remove Postgres dependencies (using uv for API venv) ==="
echo ""

# -----------------------------------------------------------------------------
# 1. Delete postgres_store and alembic
# -----------------------------------------------------------------------------
echo "1. Deleting api/app/postgres_store.py and api/alembic/..."
delete_file "$ROOT_DIR/api/app/postgres_store.py"
delete_dir "$ROOT_DIR/api/alembic"
echo ""

# -----------------------------------------------------------------------------
# 2. Remove Postgres packages from api/requirements.txt
# -----------------------------------------------------------------------------
echo "2. Removing sqlalchemy, psycopg2-binary, pgvector, alembic from api/requirements.txt..."
REQ="$ROOT_DIR/api/requirements.txt"
if [[ -f "$REQ" ]]; then
  if $APPLY; then
    sed -i.bak -e '/# PostgreSQL + pgvector/d' \
        -e '/^sqlalchemy/d' \
        -e '/^psycopg2-binary/d' \
        -e '/^pgvector/d' \
        -e '/^alembic/d' \
        "$REQ"
    rm -f "${REQ}.bak"
  fi
  echo "  - updated $REQ"
else
  echo "  - skip (missing) $REQ"
fi
echo ""

# -----------------------------------------------------------------------------
# 3. Delete postgres-only scripts
# -----------------------------------------------------------------------------
echo "3. Deleting postgres-only scripts..."
delete_file "$ROOT_DIR/scripts/fix-postgres-permissions.sh"
delete_file "$ROOT_DIR/scripts/cleanup-postgres-migrated-buckets.sh"
delete_file "$ROOT_DIR/scripts/migrate-model-status-to-postgres.sh"
echo "  (pg-admin.sh left in place for use with external Postgres if needed)"
echo ""

# -----------------------------------------------------------------------------
# 4. Update docstrings/comments
# -----------------------------------------------------------------------------
echo "4. Updating docstrings and comments..."

# analysis_templates_seed.py — remove "and postgres_store" from docstring
SEED="$ROOT_DIR/api/app/analysis_templates_seed.py"
if [[ -f "$SEED" ]]; then
  if $APPLY; then
    sed -i.bak 's/Used by storage (blob) and postgres_store. No Postgres dependency./Used by storage (blob). No Postgres dependency./' "$SEED"
    rm -f "${SEED}.bak"
  fi
  echo "  - $SEED"
fi

# -----------------------------------------------------------------------------
# 5. config.py — keep POSTGRES_URL and is_postgres_enabled() for API compatibility
#    (routers still reference them; they return "" and False). No change.
# -----------------------------------------------------------------------------
echo "5. config.py: POSTGRES_URL and is_postgres_enabled() left in place (return empty/False) for API compatibility."
echo ""

# -----------------------------------------------------------------------------
# 6. Optional: patch scripts/manual-deploy.sh
# -----------------------------------------------------------------------------
echo "6. manual-deploy.sh..."
DEPLOY="$ROOT_DIR/scripts/manual-deploy.sh"
if [[ -f "$DEPLOY" ]]; then
  if $APPLY; then
    # Remove setup-postgres from the list of valid commands in the case statement
    sed -i.bak 's/setup-postgres|//g' "$DEPLOY"
    # Remove the setup-postgres case branch (three lines: setup-postgres), setup_postgres, ;;)
    sed -i.bak '/^    setup-postgres)$/,/^        ;;$/d' "$DEPLOY"
    # Remove the help line for setup-postgres
    sed -i.bak '/setup-postgres.*Create Cloud SQL/d' "$DEPLOY"
    rm -f "${DEPLOY}.bak"
    echo "  - patched $DEPLOY (setup-postgres command and help removed)"
  else
    echo "  - run with --apply to remove setup-postgres from manual-deploy.sh"
  fi
  echo "  Manual step: In deploy_api(), set CLOUD_SQL_FLAGS and SECRET_FLAGS to empty so POSTGRES_URL is never wired."
  echo "  Manual step: In status(), remove or comment POSTGRES_URL secret wiring if present."
else
  echo "  - skip (missing) $DEPLOY"
fi
echo ""

# -----------------------------------------------------------------------------
# 7. Refresh API venv with uv (after requirements.txt was edited)
# -----------------------------------------------------------------------------
if $APPLY && [[ -f "$API_DIR/pyproject.toml" ]]; then
  echo "7. Syncing API venv with uv (remove postgres deps from env)..."
  (cd "$API_DIR" && uv sync)
  echo "  - uv sync done in api/"
  echo ""
fi

# -----------------------------------------------------------------------------
# Summary and manual steps
# -----------------------------------------------------------------------------
echo "=== Summary ==="
if $APPLY; then
  echo "Changes applied. Recommended next steps:"
  echo "  1. scripts/manual-deploy.sh: In deploy_api() (~line 769), replace the Cloud SQL block with:"
  echo "       local CLOUD_SQL_FLAGS=\"\""
  echo "       local SECRET_FLAGS=\"\""
  echo "     so POSTGRES_URL is never wired to the API service."
  echo "  2. Run API tests with uv:  cd api && uv run pytest tests/ -v"
  echo "     (venv was already synced with uv sync above)"
else
  echo "Dry run complete. Run with --apply to apply changes."
  echo "After applying, use uv in the API:  cd api && uv sync && uv run pytest tests/ -v"
fi
echo ""
echo "Note: config.py keeps POSTGRES_URL and is_postgres_enabled() (returning \"\" and False) for API compatibility."
