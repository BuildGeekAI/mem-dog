#!/usr/bin/env bash
# pg-admin.sh — PostgreSQL admin helper for mem-dog.
#
# Connects to the mem-dog PostgreSQL database and runs common inspection
# queries.  Works with:
#   - Local docker-compose (POSTGRES_URL from env or default)
#   - Cloud SQL via the Cloud SQL Auth Proxy
#
# Usage:
#   ./scripts/pg-admin.sh [command] [options]
#
# Commands:
#   status        Show row counts for all three tables
#   metadata      List data_metadata rows (most recent first)
#   embeddings    List embedding summaries grouped by data_id
#   viewpoints    List viewpoints (most recent first)
#   psql          Open an interactive psql session
#   schema        Print CREATE TABLE statements for all tables
#
# Options:
#   --url URL     PostgreSQL connection URL (defaults to POSTGRES_URL env var)
#                 or postgresql+psycopg2://memdog:memdog@localhost:5432/memdog
#   -h, --help    Show this help
#
# Cloud SQL (via Auth Proxy):
#   ./cloud-sql-proxy PROJECT:REGION:INSTANCE &
#   POSTGRES_URL="postgresql://memdog:PASS@localhost:5432/memdog" ./scripts/pg-admin.sh status
#
# Examples:
#   ./scripts/pg-admin.sh status
#   ./scripts/pg-admin.sh metadata
#   ./scripts/pg-admin.sh psql

set -euo pipefail

# ─── Defaults ────────────────────────────────────────────────────────────────
COMMAND="${1:-status}"
DEFAULT_URL="postgresql+psycopg2://memdog:memdog@localhost:5432/memdog"

# Strip SQLAlchemy driver prefix (psycopg2 / asyncpg) to get a plain libpq URL
raw_url="${POSTGRES_URL:-$DEFAULT_URL}"
PSQL_URL="${raw_url/postgresql+psycopg2:\/\//postgresql://}"
PSQL_URL="${PSQL_URL/postgresql+asyncpg:\/\//postgresql://}"

shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) PSQL_URL="$2"; shift 2 ;;
    -h|--help) grep '^# ' "$0" | sed 's/^# //'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

require_psql() {
  if ! command -v psql &>/dev/null; then
    echo "ERROR: psql not found. Install postgresql-client." >&2
    echo "  macOS:  brew install libpq && brew link --force libpq" >&2
    echo "  Ubuntu: apt-get install postgresql-client" >&2
    exit 1
  fi
}

run_sql() {
  psql "$PSQL_URL" -c "$1"
}

# ─── Commands ────────────────────────────────────────────────────────────────
case "$COMMAND" in
  status)
    require_psql
    echo "=== mem-dog Postgres status ==="
    echo "URL: ${PSQL_URL%%@*}@…"
    echo ""
    run_sql "
      SELECT
        'data_metadata' AS table_name,
        COUNT(*)        AS rows
      FROM data_metadata
      UNION ALL
      SELECT 'embeddings', COUNT(*) FROM embeddings
      UNION ALL
      SELECT 'viewpoints', COUNT(*) FROM viewpoints;
    "
    ;;

  metadata)
    require_psql
    echo "=== data_metadata (20 most recent) ==="
    run_sql "
      SELECT data_id, current_version, name, tags::text,
             LEFT(updated_at, 19) AS updated_at
      FROM data_metadata
      ORDER BY updated_at DESC
      LIMIT 20;
    "
    ;;

  embeddings)
    require_psql
    echo "=== embeddings (grouped by data_id) ==="
    run_sql "
      SELECT data_id,
             COUNT(*)       AS chunks,
             MAX(model)     AS model,
             MAX(dimensions) AS dimensions,
             LEFT(MAX(created_at), 19) AS last_created
      FROM embeddings
      GROUP BY data_id
      ORDER BY last_created DESC
      LIMIT 20;
    "
    ;;

  viewpoints)
    require_psql
    echo "=== viewpoints (20 most recent) ==="
    run_sql "
      SELECT viewpoint_id, data_id, prompt_id, model, version,
             LEFT(updated_at, 19) AS updated_at
      FROM viewpoints
      ORDER BY updated_at DESC
      LIMIT 20;
    "
    ;;

  schema)
    require_psql
    echo "=== Schema ==="
    run_sql "
      SELECT table_name, column_name, data_type, is_nullable
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name IN ('data_metadata', 'embeddings', 'viewpoints')
      ORDER BY table_name, ordinal_position;
    "
    ;;

  psql)
    require_psql
    echo "Connecting to $PSQL_URL ..."
    exec psql "$PSQL_URL"
    ;;

  *)
    echo "Unknown command: $COMMAND" >&2
    echo "Run with --help for usage." >&2
    exit 1
    ;;
esac
