#!/usr/bin/env bash
# Restore-test (REL-005): proves the newest backup is (a) byte-intact, (b) loads
# cleanly into a throwaway database, and (c) reproduces exactly what was in the
# source at dump time. An untested backup is not a backup — this is the check
# that catches the corrupted/tampered/silently-truncated dump BEFORE an outage
# depends on it. Wire it right after backup-db.sh in cron so a bad backup fails
# loudly in the log, not at 2am when you actually needed it.
#
# Usage: ./scripts/verify-backup.sh [path/to.dump]   (defaults to newest .dump)
# Exits non-zero on any mismatch.
set -euo pipefail

cd "$(dirname "$0")/.."

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-chess}"
PGDB="${POSTGRES_DB:-chess_engine}"
OUT_DIR="${BACKUP_DIR:-./backups}"

DUMP="${1:-$(ls -t "${OUT_DIR}/${PGDB}-"*.dump 2>/dev/null | head -1 || true)}"
{ [ -n "${DUMP}" ] && [ -f "${DUMP}" ]; } || { echo "FAIL: no backup to verify in ${OUT_DIR}" >&2; exit 1; }
META="${DUMP}.meta"
SCRATCH="${PGDB}_verify_$$"

runsql() { psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" "$@"; }
meta_val() { [ -f "${META}" ] && sed -n "s/^$1=//p" "${META}" | head -1 || echo ""; }

echo "Verifying ${DUMP} ..."

# 1) Byte integrity: the file matches the sha256 recorded at backup time.
if [ -f "${META}" ]; then
  WANT="$(meta_val sha256)"
  GOT="$(sha256sum "${DUMP}" | cut -d' ' -f1)"
  if [ -n "${WANT}" ] && [ "${WANT}" != "${GOT}" ]; then
    echo "FAIL: sha256 mismatch — the backup file is corrupt/truncated" >&2
    exit 2
  fi
  echo "  sha256: ok"
fi

# 2) It restores into a scratch DB, which we always tear down.
echo "  restoring into scratch ${SCRATCH} ..."
runsql -d postgres -qc "CREATE DATABASE \"${SCRATCH}\";"
cleanup() { runsql -d postgres -qc "DROP DATABASE IF EXISTS \"${SCRATCH}\";" >/dev/null 2>&1 || true; }
trap cleanup EXIT
if ! pg_restore -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${SCRATCH}" \
     --no-owner --exit-on-error "${DUMP}"; then
  echo "FAIL: pg_restore reported errors — the dump is not loadable" >&2
  exit 3
fi

# 3) Fidelity: the restored cluster must match the manifest (targets come from
#    the sidecar, never the live DB, so a write racing this run cannot make a
#    good backup look bad).
if [ -f "${META}" ]; then
  A_WANT="$(meta_val alembic)"
  if [ -n "${A_WANT}" ]; then
    A_GOT="$(runsql -d "${SCRATCH}" -tAc "select version_num from alembic_version;" 2>/dev/null || echo "")"
    if [ "${A_WANT}" != "${A_GOT}" ]; then
      echo "FAIL: alembic ${A_GOT:-none}, expected ${A_WANT}" >&2
      exit 5
    fi
    echo "  alembic: ${A_GOT} ok"
  fi
  check_rows() {
    local want="$1" table="$2" got
    [ -z "${want}" ] && return 0
    got="$(runsql -d "${SCRATCH}" -tAc "select count(*) from ${table};" 2>/dev/null || echo "-1")"
    if [ "${want}" != "${got}" ]; then
      echo "FAIL: ${table} restored ${got}, expected ${want}" >&2
      exit 4
    fi
    echo "  ${table}: ${got} rows ok"
  }
  check_rows "$(meta_val rows_users)" users
  check_rows "$(meta_val rows_games)" games
  check_rows "$(meta_val rows_game_moves)" game_moves
fi

echo "PASS: ${DUMP} restores clean and matches its manifest."
