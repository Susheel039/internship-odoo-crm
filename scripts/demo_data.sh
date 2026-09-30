#!/usr/bin/env bash
# Load the demo story: the workflow (universities, companies, students, placements in every
# stage) and 30 CRM leads with their pipeline journeys.
# Usage: scripts/demo_data.sh [db]   (default: internship_dev). Takes a backup first.
source "$(dirname "$0")/_lib.sh"

DB="${1:-$DEFAULT_DB}"
require_running "$ODOO_CONTAINER" "$DB_CONTAINER"
db_exists "$DB" || die "Database '$DB' does not exist. Create it with: scripts/init_db.sh $DB"

log "Backing up '$DB' first"
"$REPO_ROOT/scripts/backup_db.sh" "$DB" | tail -1

for script in seed_workflow_demo.py seed_crm_journeys.py; do
  log "Running $script on '$DB'"
  docker cp "$REPO_ROOT/scripts/demo/$script" "$ODOO_CONTAINER:/tmp/$script"
  docker exec -i "$ODOO_CONTAINER" bash -c \
    'odoo shell --config /etc/odoo/odoo.conf --db_host "$HOST" --db_port "${PORT:-5432}" --db_user "$USER" --db_password "$PASSWORD" -d "$1" --no-http < "/tmp/$2"' \
    odoo "$DB" "$script" 2>&1 | grep -E '^SEED|Traceback|Error:' || true
done
