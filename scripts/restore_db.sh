#!/usr/bin/env bash
# Restore a backup made by backup_db.sh.
# Usage: scripts/restore_db.sh <backup_dir> [target_db] [--force]
#   target_db defaults to the name the backup was taken from.
#   An existing target is only replaced with --force.
source "$(dirname "$0")/_lib.sh"

SRC="${1:-}"
[[ -n "$SRC" && -f "$SRC/db.dump" ]] || die "Usage: $0 <backup_dir> [target_db] [--force]"
shift
FORCE=0
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    *) TARGET="$arg" ;;
  esac
done
if [[ -z "$TARGET" ]]; then
  TARGET="$(basename "$SRC")"
  TARGET="${TARGET%_*_*}"  # strip _<date>_<time>
fi

require_running "$DB_CONTAINER" "$ODOO_CONTAINER"

if db_exists "$TARGET"; then
  [[ $FORCE -eq 1 ]] || die "Database '$TARGET' exists. Re-run with --force to replace it."
  log "Dropping existing database '$TARGET'"
  psql_q "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TARGET' AND pid <> pg_backend_pid()" > /dev/null
  pg_exec "$DB_CONTAINER" dropdb -U "$PG_USER" "$TARGET"
fi

log "Restoring '$SRC' into '$TARGET'"
pg_exec "$DB_CONTAINER" createdb -U "$PG_USER" "$TARGET"
pg_exec -i "$DB_CONTAINER" pg_restore -U "$PG_USER" -d "$TARGET" --no-owner < "$SRC/db.dump"

if [[ -f "$SRC/filestore.tar.gz" ]]; then
  log "Restoring filestore"
  SRC_DB="$(tar -tzf "$SRC/filestore.tar.gz" | head -1 | cut -d/ -f1)"
  docker exec "$ODOO_CONTAINER" rm -rf "$FILESTORE_ROOT/$TARGET"
  docker exec -i "$ODOO_CONTAINER" bash -c "mkdir -p '$FILESTORE_ROOT/.restore_tmp' && tar -C '$FILESTORE_ROOT/.restore_tmp' -xzf - \
    && mv '$FILESTORE_ROOT/.restore_tmp/$SRC_DB' '$FILESTORE_ROOT/$TARGET' && rmdir '$FILESTORE_ROOT/.restore_tmp'" \
    < "$SRC/filestore.tar.gz"
fi

log "Restore complete: '$TARGET'"
