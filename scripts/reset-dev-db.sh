#!/usr/bin/env bash
# Rebuild the local development schema from migrations (REL-006).
#
# The target database is resolved from app settings, so this script can never
# drift from what the API and `alembic` actually use: DATABASE_URL /
# database_url wins, then apps/api/.env, then the neutral default.
#
# Since tests/conftest.py now refuses to run against anything but a throwaway
# database, this is only needed after an intentional manual reset or a
# half-applied migration locally. It drops ALL tables in the target schema.
set -euo pipefail

cd "$(dirname "$0")/../apps/api"
source .venv/bin/activate

DSN="$(python -c 'from app.core.database import settings; print(settings.database_url)')"
# psql speaks libpq URIs; drop the SQLAlchemy driver suffix.
PSQL_DSN="${DSN/postgresql+psycopg:/postgresql:}"
DB_NAME="$(python -c 'import sys; from sqlalchemy.engine import make_url; print(make_url(sys.argv[1]).database)' "$DSN")"

echo "Target database: ${DB_NAME}"
case "$DB_NAME" in
  postgres|template0|template1|chess_test)
    echo "Refusing to reset ${DB_NAME}: it is a maintenance or test database." >&2
    exit 1
    ;;
esac

if [[ "${YES:-}" != "1" ]]; then
  read -r -p "Drop and recreate every table in ${DB_NAME}? Set YES=1 to skip this prompt. [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

psql "$PSQL_DSN" -v ON_ERROR_STOP=1 -c 'DROP SCHEMA IF EXISTS public CASCADE;' -c 'CREATE SCHEMA public;'
alembic upgrade head

echo "Tables now present:"
psql "$PSQL_DSN" -tAc \
  "select tablename from pg_tables where schemaname='public' order by tablename;"
