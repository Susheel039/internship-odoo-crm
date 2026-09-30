#!/usr/bin/env bash
# Back up a database (pg_dump custom format) and its filestore.
# Usage: scripts/backup_db.sh [db]    -> backups/<db>_<timestamp>/{db.dump,filestore.tar.gz}
source "$(dirname "$0")/_lib.sh"

DB="${1:-$DEFAULT_DB}"
require_running "$DB_CONTAINER" "$ODOO_CONTAINER"
db_exists "$DB" || die "Database '$DB' does not exist."

DEST="$BACKUP_ROOT/${DB}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DEST"

log "Dumping database '$DB'"
pg_exec "$DB_CONTAINER" pg_dump -U "$PG_USER" -Fc --no-owner "$DB" > "$DEST/db.dump"
# Fail loudly on an empty or unreadable dump rather than leaving a useless backup.
pg_exec -i "$DB_CONTAINER" pg_restore --list < "$DEST/db.dump" > /dev/null \
  || die "Dump verification failed: $DEST/db.dump"

if docker exec "$ODOO_CONTAINER" test -d "$FILESTORE_ROOT/$DB"; then
  log "Archiving filestore"
  docker exec "$ODOO_CONTAINER" tar -C "$FILESTORE_ROOT" -czf - "$DB" > "$DEST/filestore.tar.gz"
else
  log "No filestore for '$DB' (nothing to archive)"
fi

log "Backup complete: $DEST ($(du -sh "$DEST" | cut -f1))"
echo "$DEST"
