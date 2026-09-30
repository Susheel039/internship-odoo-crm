# shellcheck shell=bash
# Shared helpers for the scripts in this folder. Source it, don't run it.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Load .env (gitignored) so the scripts use the same credentials as docker compose.
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

ODOO_CONTAINER="${ODOO_CONTAINER:-internship_odoo}"
DB_CONTAINER="${DB_CONTAINER:-internship_postgres}"
PG_USER="${POSTGRES_USER:-odoo}"
DEFAULT_DB="${ODOO_DB:-internship_dev}"
FILESTORE_ROOT="/var/lib/odoo/filestore"
BACKUP_ROOT="${BACKUP_ROOT:-$REPO_ROOT/backups}"
# A spare HTTP port so CLI runs inside the container don't clash with the live server on 8069.
CLI_HTTP_PORT="${CLI_HTTP_PORT:-8070}"

# Dependency order. New v2 modules are installed (-i) on upgrade, existing ones updated (-u).
INTERNSHIP_MODULES=(
  internship_base
  internship_placement
  internship_agreement
  internship_crm
  internship_monitoring
  internship_completion
  internship_vapi
  internship_reporting
  internship_portal
)

log() { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

join_by() { local IFS="$1"; shift; echo "$*"; }
all_modules_csv() { join_by , "${INTERNSHIP_MODULES[@]}"; }
# "/internship_base,/internship_crm,..." for --test-tags
test_tags_for() { local m out=(); for m in "$@"; do out+=("/$m"); done; join_by , "${out[@]}"; }

require_running() {
  local c
  for c in "$@"; do
    docker ps --format '{{.Names}}' | grep -qx "$c" || die "Container '$c' is not running. Start the stack: make up"
  done
}

# The postgres image's perl pg_wrapper warns about the locale on every call; pin it.
pg_exec() { docker exec -e LC_ALL=C.UTF-8 "$@"; }

psql_q() { pg_exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d postgres -Atc "$1"; }
db_exists() { [[ "$(psql_q "SELECT 1 FROM pg_database WHERE datname = '$1'")" == "1" ]]; }

# Drop a database and its filestore (used to clean up temporary test copies).
drop_db() {
  local db="$1"
  db_exists "$db" || return 0
  psql_q "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid()" > /dev/null
  pg_exec "$DB_CONTAINER" dropdb -U "$PG_USER" "$db"
  docker exec "$ODOO_CONTAINER" rm -rf "$FILESTORE_ROOT/$db"
}

# Run the odoo CLI inside the running container. `docker exec` bypasses the image
# entrypoint, so pass the DB connection explicitly from the container's own env.
odoo_cli() {
  docker exec -i "$ODOO_CONTAINER" bash -c \
    'exec odoo --config /etc/odoo/odoo.conf --db_host "$HOST" --db_port "${PORT:-5432}" --db_user "$USER" --db_password "$PASSWORD" "$@"' \
    odoo "$@"
}

# Run Odoo tests and fail on test failures or ERROR/CRITICAL log lines.
# Usage: run_odoo_tests <db> <-i|-u> <modules_csv> <test_tags> [extra odoo args...]
run_odoo_tests() {
  local db="$1" mode="$2" modules="$3" tags="$4"
  shift 4
  local logfile status=0
  logfile="$(mktemp -t odoo-test.XXXXXX)"
  log "Running tests on '$db' ($mode $modules, tags $tags)"
  local mode_args=("$mode" "$modules")
  # On upgrade, also install modules that are new in this version (a no-op for installed ones).
  [[ "$mode" == "-u" ]] && mode_args=(-i "$modules" -u "$modules")
  # --db-filter: the web tests must reach this temporary database (the live server only serves internship_dev).
  odoo_cli -d "$db" "${mode_args[@]}" --db-filter "^${db}\$" --test-enable --test-tags "$tags" \
    --stop-after-init --http-port="$CLI_HTTP_PORT" --log-level=test "$@" 2>&1 | tee "$logfile" || status=$?
  if [[ $status -ne 0 ]] || grep -qE '^[0-9-]+ [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' "$logfile"; then
    echo
    grep -E '(ERROR|CRITICAL|FAIL)' "$logfile" | head -40 || true
    rm -f "$logfile"
    die "Tests FAILED on '$db' (exit $status)"
  fi
  grep -E 'tests? .*(passed|failed)|Ran [0-9]+ test|[0-9]+ failed, [0-9]+ error' "$logfile" | tail -3 || true
  rm -f "$logfile"
  log "Tests passed on '$db'"
}
