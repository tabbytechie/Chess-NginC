# Chess Engine API

FastAPI backend for the chess engine project. Modular monolith under `/api/v1`.

## Prerequisites

- Python 3.12+
- PostgreSQL 14+ running locally, **or** the compose stack from the repo root
  (`docker compose up db`)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Point the app at a database by creating an untracked `apps/api/.env` (it is read
by absolute path, so it works from any working directory):

```bash
cp ../../.env.example .env   # then edit
# minimum needed:
#   database_url=postgresql+psycopg://<user>:<password>@localhost:5432/<db>
```

Precedence: `DATABASE_URL` / `database_url` environment variable → `apps/api/.env`
→ the neutral default in `app/core/database.py`. `alembic` resolves the URL the
same way, so migrations can never target a different database than the API.

Apply migrations:

```bash
alembic upgrade head
alembic check     # fails if models and migrations have drifted
```

## Run

```bash
uvicorn app.main:app --reload
```

OpenAPI docs are served at `/docs`. The frontend dev server proxies `/api` here,
so no extra configuration is needed on the web side.

## Tests

The suite runs against a **live PostgreSQL** database and drops/recreates every
table between tests, so it refuses to run against anything but a throwaway
database:

```bash
pytest                    # uses $database_url, else .../chess_test (created for you)
pytest -q tests/test_games.py
```

If you export `database_url` pointing at `chess`, `chess_engine`, or `postgres`,
collection fails with an explanation rather than wiping your data. To rebuild
the development schema deliberately:

```bash
../../scripts/reset-dev-db.sh
```

## Checks

```bash
ruff check app tests && ruff format --check app tests
mypy app
pytest
```

## Layout

```
app/api/v1/     routes, schemas, dependencies (HTTP layer)
app/auth/       registration, login, sessions, validators
app/games/      rules adapter, service, domain, errors
app/engine/     search, evaluation, Stockfish UCI adapter, providers
app/models/     SQLAlchemy tables
app/repositories/ persistence
app/core/       settings, engine, session
alembic/        migrations
```
