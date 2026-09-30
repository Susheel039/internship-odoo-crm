#!/usr/bin/env bash
# Load the workflow demo data (leads, placements in every stage, calls, ...) into a DEMO database.
# Usage: scripts/demo_data.sh <db>   Refuses to run on internship_dev.
source "$(dirname "$0")/_lib.sh"

DB="${1:-}"
[[ -n "$DB" ]] || die "Usage: $0 <demo_db>"
[[ "$DB" != "$DEFAULT_DB" ]] || die "Refusing to load demo data into '$DEFAULT_DB'. Use a demo database."
require_running "$ODOO_CONTAINER"
db_exists "$DB" || die "Database '$DB' does not exist. Create it with: scripts/init_db.sh $DB --demo"

docker cp "$REPO_ROOT/scripts/demo/seed_workflow_demo.py" "$ODOO_CONTAINER:/tmp/seed_workflow_demo.py"
docker exec -i "$ODOO_CONTAINER" bash -c \
  'odoo shell --config /etc/odoo/odoo.conf --db_host "$HOST" --db_port "${PORT:-5432}" --db_user "$USER" --db_password "$PASSWORD" -d "$1" --no-http < /tmp/seed_workflow_demo.py' \
  odoo "$DB" 2>&1 | grep -E '^SEED|Traceback|Error' || true
