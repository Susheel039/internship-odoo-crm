#!/usr/bin/env bash
# Clone a database and its filestore for safe testing.
# Usage: scripts/clone_db.sh <src> <dst> [--no-neutralize]
#   The clone is neutralized by default (crons off, outgoing mail disabled) so it
#   never sends email or places Vapi calls while you test on it.
#   An existing <dst> is dropped and recreated.
source "$(dirname "$0")/_lib.sh"

SRC="${1:-}"
DST="${2:-}"
NEUTRALIZE=1
[[ "${3:-}" == "--no-neutralize" ]] && NEUTRALIZE=0
[[ -n "$SRC" && -n "$DST" ]] || die "Usage: $0 <src> <dst> [--no-neutralize]"
[[ "$SRC" != "$DST" ]] || die "Source and destination must differ."

require_running "$DB_CONTAINER" "$ODOO_CONTAINER"
db_exists "$SRC" || die "Source database '$SRC' does not exist."

if db_exists "$DST"; then
  log "Dropping existing clone '$DST'"
  psql_q "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DST' AND pid <> pg_backend_pid()" > /dev/null
  pg_exec "$DB_CONTAINER" dropdb -U "$PG_USER" "$DST"
fi

log "Cloning '$SRC' -> '$DST'"
# createdb -T is fastest but needs the source to have no open sessions. The live Odoo
# server usually has some, so fall back to dump/restore instead of killing them.
if ! pg_exec "$DB_CONTAINER" createdb -U "$PG_USER" -T "$SRC" "$DST" 2> /dev/null; then
  log "Source is in use; cloning with pg_dump | pg_restore instead"
  pg_exec "$DB_CONTAINER" createdb -U "$PG_USER" "$DST"
  pg_exec "$DB_CONTAINER" bash -c \
    "pg_dump -U '$PG_USER' -Fc --no-owner '$SRC' | pg_restore -U '$PG_USER' -d '$DST' --no-owner"
fi

# A distinct uuid keeps the clone from being mistaken for the original.
psql_uuid="UPDATE ir_config_parameter SET value = gen_random_uuid()::text WHERE key = 'database.uuid'"
pg_exec "$DB_CONTAINER" psql -U "$PG_USER" -d "$DST" -qc "$psql_uuid" > /dev/null

if docker exec "$ODOO_CONTAINER" test -d "$FILESTORE_ROOT/$SRC"; then
  log "Copying filestore"
  docker exec "$ODOO_CONTAINER" bash -c "rm -rf '$FILESTORE_ROOT/$DST' && cp -a '$FILESTORE_ROOT/$SRC' '$FILESTORE_ROOT/$DST'"
fi

if [[ $NEUTRALIZE -eq 1 ]]; then
  log "Neutralizing clone"
  docker exec -i "$ODOO_CONTAINER" bash -c \
    'odoo neutralize --config /etc/odoo/odoo.conf --db_host "$HOST" --db_port "${PORT:-5432}" --db_user "$USER" --db_password "$PASSWORD" -d "$1"' \
    odoo "$DST" > /dev/null 2>&1 || die "Neutralize failed on '$DST'"
fi

log "Clone ready: '$DST'"
