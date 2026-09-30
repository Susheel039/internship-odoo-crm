#!/usr/bin/env bash
# Run module tests.
# Usage: scripts/test.sh [module|all] [--db <existing_db>]
#   Default: drop and recreate a throwaway DB 'internship_test', install with demo data
#   (same as CI). With --db: upgrade (-u) that existing database and test it; never
#   point this at a database you care about, use a clone.
source "$(dirname "$0")/_lib.sh"

TARGET="all"
DB=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB="${2:-}"; shift 2 ;;
    -*) die "Unknown option: $1" ;;
    *) TARGET="$1"; shift ;;
  esac
done

if [[ "$TARGET" == "all" ]]; then
  MODULES=("${INTERNSHIP_MODULES[@]}")
else
  [[ -d "$REPO_ROOT/custom_addons/$TARGET" ]] || die "Unknown module '$TARGET'"
  MODULES=("$TARGET")
fi
MODULES_CSV="$(join_by , "${MODULES[@]}")"
TAGS="$(test_tags_for "${MODULES[@]}")"

require_running "$DB_CONTAINER" "$ODOO_CONTAINER"

if [[ -n "$DB" ]]; then
  [[ "$DB" != "$DEFAULT_DB" ]] || die "Refusing to test directly on '$DEFAULT_DB'. Clone it first (make upgrade)."
  db_exists "$DB" || die "Database '$DB' does not exist."
  run_odoo_tests "$DB" -u "$MODULES_CSV" "$TAGS"
else
  DB="internship_test"
  if db_exists "$DB"; then
    psql_q "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB' AND pid <> pg_backend_pid()" > /dev/null
    pg_exec "$DB_CONTAINER" dropdb -U "$PG_USER" "$DB"
    docker exec "$ODOO_CONTAINER" rm -rf "$FILESTORE_ROOT/$DB"
  fi
  run_odoo_tests "$DB" -i "$MODULES_CSV" "$TAGS" --with-demo
fi
