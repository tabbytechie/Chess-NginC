#!/usr/bin/env bash
# Point-in-time RECOVERY (PITR). Stands up a THROWAWAY Postgres replayed to a
# chosen instant from a base backup + the WAL archive — NEVER over the live
# database — so you can check (or rescue) "the DB as it was at 03:00", not just
# the last nightly dump. This is the drill that makes item 2 real.
#
# Requires: compose.pitr.yaml archiving (WAL in ./wal-archive), one
# scripts/pitr-basebackup.sh run, and Docker (a throwaway container does the
# replay, so nothing installed is touched).
#
# Usage: PITR_TARGET="2026-10-26 03:00:00+00" ./scripts/pitr-restore.sh [base.tar]
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="${PITR_TARGET:?set PITR_TARGET, e.g. PITR_TARGET=\"2026-10-26 03:00:00+00\"}"
BASE="${1:-$(ls -t ./backups/base/base-*.tar 2>/dev/null | head -1 || true)}"
[ -n "${BASE}" ] && [ -f "${BASE}" ] || { echo "no base backup under ./backups/base (run pitr-basebackup.sh)" >&2; exit 1; }
[ -d ./wal-archive ] || { echo "no ./wal-archive (enable compose.pitr.yaml, then generate some writes)" >&2; exit 1; }

IMAGE="${POSTGRES_IMAGE:-postgres:18-alpine}"
PORT="${PITR_PORT:-5433}"
DATA="./pitr-recovery/data"
rm -rf ./pitr-recovery
mkdir -p "${DATA}"

echo "Extracting ${BASE} ..."
TMP="$(mktemp -d)"
tar -xf "${BASE}" -C "${TMP}"                 # -> postgresql.tar.gz (+ tablespaces)
tar -xzf "${TMP}/postgresql.tar.gz" -C "${DATA}"
rm -rf "${TMP}"

# Archive recovery: replay WAL from the read-only archive up to the target, then
# promote so the scratch cluster is queryable.
cat >> "${DATA}/postgresql.auto.conf" <<EOF
restore_command = 'cp /wal_archive/%f %p'
recovery_target_time = '${TARGET}'
recovery_target_action = 'promote'
EOF
: > "${DATA}/recovery.signal"

echo "Starting throwaway recovery on :${PORT} (data stays in ${DATA}, live DB untouched) ..."
docker run --rm -d --name chess-pitr -p "${PORT}:5432" \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  -v "${PWD}/${DATA}:/var/lib/postgresql/data" \
  -v "${PWD}/wal-archive:/wal_archive:ro" \
  "${IMAGE}"

cat <<EOF

Next steps:
  watch:   docker logs -f chess-pitr      # wait for 'database system is ready'
  verify:  psql 'postgresql://postgres@localhost:${PORT}/postgres' -tAc 'select now()'
  promote: it self-promotes at the target time (recovery_target_action=promote)
  cleanup: docker stop chess-pitr && rm -rf ./pitr-recovery
Linux: the extracted datadir must be owned by the container postgres uid (999):
       sudo chown -R 999:999 ./pitr-recovery   (Docker Desktop/macOS: no-op)
EOF
