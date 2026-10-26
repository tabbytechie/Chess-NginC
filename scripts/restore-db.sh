#!/usr/bin/env bash
# Restore a DB backup into a target database (REL-005/REL-014).
# Handles both custom-format `.dump` (pg_dump -Fc, via pg_restore) and legacy
# plain `.sql` (via psql), so old and new backups both load.
#
# Usage: ./scripts/restore-db.sh <backup.dump|backup.sql> [target_db]
# NEVER restore over production without a fresh backup first.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP="${1:?usage: restore-db.sh <backup.dump|backup.sql> [target_db]}"
TARGET="${2:-${POSTGRES_DB:-chess_engine}_restore}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-chess}"

test -f "${BACKUP}" || { echo "Backup not found: ${BACKUP}" >&2; exit 1; }

echo "Creating restore target ${TARGET} ..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres \
  -c "DROP DATABASE IF EXISTS \"${TARGET}\";" \
  -c "CREATE DATABASE \"${TARGET}\";"

case "${BACKUP}" in
  *.dump)
    echo "Restoring custom-format ${BACKUP} -> ${TARGET} (pg_restore) ..."
    pg_restore -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${TARGET}" \
      --no-owner --exit-on-error "${BACKUP}"
    ;;
  *)
    echo "Restoring plain SQL ${BACKUP} -> ${TARGET} (psql) ..."
    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${TARGET}" -f "${BACKUP}" >/dev/null
    ;;
esac

echo "Row counts after restore:"
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${TARGET}" -tAc \
  "select 'users=' || count(*) from users; select 'games=' || count(*) from games; select 'game_moves=' || count(*) from game_moves;" \
  2>/dev/null || echo "(table counts unavailable — schema may differ; inspect manually)"
echo "Restore complete: ${TARGET}"
