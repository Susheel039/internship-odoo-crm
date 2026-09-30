#!/usr/bin/env bash
# Create the development database and install every internship module.
# Usage: scripts/init_db.sh [db] [--demo]
#   Refuses to touch a database that already exists (use upgrade.sh for that).
source "$(dirname "$0")/_lib.sh"

DB="$DEFAULT_DB"
DEMO_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --demo) DEMO_ARGS=(--with-demo) ;;
    -*) die "Unknown option: $arg" ;;
    *) DB="$arg" ;;
  esac
done

require_running "$DB_CONTAINER" "$ODOO_CONTAINER"
if db_exists "$DB"; then
  die "Database '$DB' already exists. Use 'make upgrade' to update it, or pick another name."
fi

log "Creating '$DB' and installing: $(all_modules_csv)"
# ${arr[@]+...} keeps macOS bash 3.2 happy with an empty array under set -u.
odoo_cli -d "$DB" -i "$(all_modules_csv)" ${DEMO_ARGS[@]+"${DEMO_ARGS[@]}"} \
  --load-language=en_GB --stop-after-init --http-port="$CLI_HTTP_PORT"

# Log in with admin / admin, then change the password immediately.
log "Database '$DB' ready at http://localhost:8069 (login: admin / admin). Change the admin password now."
