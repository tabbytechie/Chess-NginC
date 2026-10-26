#!/usr/bin/env bash
# Nightly DB backup (REL-004): a compressed custom-format dump plus an integrity
# manifest, so a silent corruption is caught later by verify-backup.sh rather
# than during the outage you actually needed the backup for.
#
# Output:
#   backups/<db>-<utcstamp>.dump        pg_dump -Fc (already compressed)
#   backups/<db>-<utcstamp>.dump.meta   sha256 + alembic version + core row
#                                       counts captured at the dump moment
#
# Modes:
#   host (default)      uses local pg_dump/psql against PGHOST/PGPORT.
#   DB_IN_CONTAINER=1   shells into the compose `db` service (no local pg_dump
#                       needed):  DB_IN_CONTAINER=1 docker compose ... ; this
#                       script then calls `docker compose exec -T db` itself.
#
# Optional offsite copy: set RCLONE_TARGET (e.g. "s3:chess-backups") to push the
# dump + sidecar to object storage after writing locally.
#
# Usage: POSTGRES_USER=chess POSTGRES_DB=chess_engine ./scripts/backup-db.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-chess}"
PGDB="${POSTGRES_DB:-chess_engine}"
OUT_DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/${PGDB}-${STAMP}.dump"

# pg_dump / psql, either on the host or inside the compose `db` container.
if [ "${DB_IN_CONTAINER:-0}" = "1" ]; then
  dump_cmd()   { docker compose exec -T db pg_dump -U "${PGUSER}" -d "${PGDB}" -Fc; }
  scalar_cmd() { docker compose exec -T db psql -U "${PGUSER}" -d "${PGDB}" -tAc "$1"; }
else
  dump_cmd()   { pg_dump -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDB}" -Fc; }
  scalar_cmd() { psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDB}" -tAc "$1"; }
fi

mkdir -p "${OUT_DIR}"
echo "Backing up ${PGDB} -> ${OUT_FILE} ..."
dump_cmd > "${OUT_FILE}"

# Integrity manifest: everything below is measured against the LIVE database at
# the same instant as the dump, so verify-backup.sh has a fixed target to compare
# a restore against (never the live DB, which may have moved on).
SHA="$(sha256sum "${OUT_FILE}" | cut -d' ' -f1)"
ALEMBIC="$(scalar_cmd "select version_num from alembic_version;" 2>/dev/null || echo "")"
USERS="$(scalar_cmd "select count(*) from users;" 2>/dev/null || echo "")"
GAMES="$(scalar_cmd "select count(*) from games;" 2>/dev/null || echo "")"
MOVES="$(scalar_cmd "select count(*) from game_moves;" 2>/dev/null || echo "")"
cat > "${OUT_FILE}.meta" <<EOF
file=$(basename "${OUT_FILE}")
sha256=${SHA}
alembic=${ALEMBIC}
rows_users=${USERS}
rows_games=${GAMES}
rows_game_moves=${MOVES}
created_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

# Optional offsite copy (3-2-1: only the dump + its sidecar travel).
if [ -n "${RCLONE_TARGET:-}" ]; then
  rclone copyto "${OUT_FILE}" "${RCLONE_TARGET}/${PGDB}-${STAMP}.dump"
  rclone copyto "${OUT_FILE}.meta" "${RCLONE_TARGET}/${PGDB}-${STAMP}.dump.meta"
fi

# Retention (REL-014): keep the newest N dump+meta pairs, drop the rest.
KEEP="${BACKUP_KEEP:-14}"
ls -t "${OUT_DIR}/${PGDB}-"*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "${old}" "${old}.meta"
done

echo "OK: ${OUT_FILE} ($(du -h "${OUT_FILE}" | cut -f1)), sha256=${SHA:0:12}…, alembic=${ALEMBIC:-?}"
echo "Retention: keeping newest ${KEEP}."
