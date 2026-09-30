#!/usr/bin/env bash
# Safe upgrade: backup -> clone -> upgrade + test the clone -> (optionally) upgrade the real DB.
# Usage: scripts/upgrade.sh [db] [--apply] [--legacy-fixture]
#   Without --apply only the clone <db>_upgrade_test is touched.
#   --legacy-fixture loads scripts/fixtures/legacy_v1.sql into the CLONE before upgrading,
#   so the v2 migrations are exercised on pre-v2 rows. Cannot be combined with --apply.
source "$(dirname "$0")/_lib.sh"

APPLY=0
FIXTURE=0
DB="$DEFAULT_DB"
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --legacy-fixture) FIXTURE=1 ;;
    -*) die "Unknown option: $arg" ;;
    *) DB="$arg" ;;
  esac
done
[[ $APPLY -eq 1 && $FIXTURE -eq 1 ]] && die "--legacy-fixture is for clone testing only; drop --apply."
CLONE="${DB}_upgrade_test"
MODULES="$(all_modules_csv)"

require_running "$DB_CONTAINER" "$ODOO_CONTAINER"
db_exists "$DB" || die "Database '$DB' does not exist."

log "Step 1/4: backup '$DB'"
"$REPO_ROOT/scripts/backup_db.sh" "$DB" | tail -1

# The clone is temporary: removed when the script ends (KEEP_CLONE=1 keeps it for inspection).
[[ "${KEEP_CLONE:-0}" == "1" ]] || trap 'drop_db "$CLONE"' EXIT

log "Step 2/4: clone '$DB' -> '$CLONE'"
"$REPO_ROOT/scripts/clone_db.sh" "$DB" "$CLONE"
if [[ $FIXTURE -eq 1 ]]; then
  log "Loading legacy v1 fixture into '$CLONE'"
  pg_exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -q -U "$PG_USER" -d "$CLONE" \
    < "$REPO_ROOT/scripts/fixtures/legacy_v1.sql" > /dev/null
fi

log "Step 3/4: upgrade + test on '$CLONE'"
run_odoo_tests "$CLONE" -u "$MODULES" "$(test_tags_for "${INTERNSHIP_MODULES[@]}")"

log "Module versions on '$CLONE':"
pg_exec "$DB_CONTAINER" psql -U "$PG_USER" -d "$CLONE" -Atc \
  "SELECT name || '  ' || state || '  ' || coalesce(latest_version, '-') FROM ir_module_module WHERE name LIKE 'internship%' ORDER BY name"

if [[ $APPLY -eq 0 ]]; then
  log "Clone upgrade OK. '$DB' was NOT changed. Re-run with --apply to upgrade it."
  exit 0
fi

log "Step 4/4: upgrading '$DB' (backup taken in step 1)"
odoo_cli -d "$DB" -i "$MODULES" -u "$MODULES" --stop-after-init --http-port="$CLI_HTTP_PORT"
log "Restart Odoo to load the new registry: docker restart $ODOO_CONTAINER"
log "Upgrade of '$DB' complete."
