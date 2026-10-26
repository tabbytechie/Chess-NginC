#!/usr/bin/env bash
# Point-in-time base backup (PITR prerequisite). A streaming base backup with
# the WAL generated during the copy embedded (-X stream), so this tarball plus
# the WAL archive (compose.pitr.yaml -> ./wal-archive) forms a consistent set
# you can replay forward to any instant. Run it on a schedule (weekly is plenty
# when paired with continuous archiving) and ship it off-host.
#
# Usage: ./scripts/pitr-basebackup.sh [out_dir]
#   DB_IN_CONTAINER=1  run pg_basebackup inside the compose `db` service.
#   RCLONE_TARGET=s3:…  push the base backup to object storage afterwards.
set -euo pipefail

cd "$(dirname "$0")/.."

PGUSER="${POSTGRES_USER:-chess}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${1:-./backups/base}"
LABEL="base-${STAMP}"
TAR="${OUT_DIR}/${LABEL}.tar"

mkdir -p "${OUT_DIR}"
echo "Base backup ${LABEL} -> ${TAR} ..."
if [ "${DB_IN_CONTAINER:-0}" = "1" ]; then
  docker compose exec -T db pg_basebackup -U "${PGUSER}" -D - -Ft -z -X stream -l "${LABEL}" > "${TAR}"
else
  pg_basebackup -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -D - -Ft -z -X stream -l "${LABEL}" > "${TAR}"
fi

if [ -n "${RCLONE_TARGET:-}" ]; then
  rclone copyto "${TAR}" "${RCLONE_TARGET}/base/${LABEL}.tar"
fi

echo "OK: ${TAR} ($(du -h "${TAR}" | cut -f1)). Keep ./wal-archive alongside it for PITR."
