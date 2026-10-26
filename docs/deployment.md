# Deployment & Operations (Phase 9, REL-001..017)

> How to ship this project: production config, secrets, HTTPS, backups,
> migrations, health checks, logging, monitoring, Stockfish licensing, CORS,
> smoke tests, rollback, and release notes.

## 1. Production configuration (REL-001)

| Setting | Source | Production value |
|---------|--------|------------------|
| `APP_ENV` | env | `production` |
| `SECRET_KEY` | env/secret store | unique ≥32 random chars (app refuses to start without it, REL-002) |
| `DATABASE_URL` / `database_url` | env | managed Postgres DSN (psycopg URL) |
| `CORS_ORIGINS` | env | exact public origin(s), e.g. `https://chess.example.com` (REL-012) |
| `COOKIE_SECURE` | env | `true` (cookies only over HTTPS, REL-012) |
| `LOG_LEVEL` | env | `INFO` (or `WARNING`) |
| `STOCKFISH_PATH` | env | absolute path; empty = PATH lookup, then distro package paths; never from clients |
| `STOCKFISH_API_KEY` | env/secret store | hosted Stockfish (stockfishapi.com) Bearer key; **only** used as fallback when no local binary is found; empty = cloud disabled; never logged or returned |
| `STOCKFISH_API_BASE_URL` | env | hosted API base, default `https://stockfishapi.com/v1` |
| `REVIEW_RATE_LIMIT_PER_HOUR` | env | per-user review **generation** budget per hour (default 10; a forced re-run costs 2) — the engine-holding surface, RL-001 |
| `TRAINING_RATE_LIMIT_PER_MINUTE` | env | per-user training-attempt budget per minute (default 60), RL-002 |
| `CLOUD_DAILY_UNIT_BUDGET` | env | app-wide cap on hosted-engine units per UTC day (default 1800 of the free plan's 2000; `0` = unlimited, use with a paid plan), RL-003 |
| `LOG_JSON` | env | `true` (default) emits JSON log lines with `request_id`; `false` restores the text format (MON-001) |

Copy `.env.example` → `.env` for local dev only. **Never commit `.env`.**

## 2. Secret management (REL-002)

- Secrets live in the deployment platform's secret store (Compose `env_file`,
  Docker secrets, or cloud KMS) — never in git, images, or logs.
- Rotate `SECRET_KEY` by: set new value → rolling restart → all sessions
  re-login (opaque tokens; rotation safely invalidates old ones).
- DB passwords rotate at the database, then update the secret and restart.

## 3. HTTPS (REL-003)

TLS terminates at the reverse proxy / load balancer in front of `web` + `api`:

1. Provision a certificate (e.g. Let's Encrypt) for the public hostname.
2. Uncomment the `return 301 https://...` redirect in `apps/web/nginx.conf`.
3. Set `COOKIE_SECURE=true` and exact `CORS_ORIGINS` (no wildcards with cookies).
4. Verify: `curl -sI http://<host>` → `301`; `https://<host>` → `200`.

## 4. Backups, restoration & PITR (REL-004/REL-005)

An untested backup is not a backup, so the default path is dump **then verify**
in one chain, with PITR as a separate opt-in for when losing a day of games is
not acceptable.

- **Backup:** `./scripts/backup-db.sh` writes a compressed custom-format dump
  (`pg_dump -Fc`) to `./backups/<db>-<utc>.dump` **plus a `.dump.meta` sidecar**
  (sha256, alembic version, core row counts captured at dump time). Keeps the
  newest `BACKUP_KEEP` (default 14). `DB_IN_CONTAINER=1` dumps through the
  compose `db` service (no local `pg_dump` needed); `RCLONE_TARGET=s3:…` pushes
  the dump + sidecar off-host.
- **Restore-test (run after every backup):** `./scripts/verify-backup.sh`
  restores the newest (or named) dump into a throwaway DB and asserts sha256,
  `alembic_version` and row counts match the sidecar, then drops it. Non-zero on
  any mismatch — this is the check that makes the backup trustworthy.
- **Restore for real:** `./scripts/restore-db.sh <backup.dump|.sql> [target_db]`
  (`pg_restore` for `.dump`, `psql` for legacy `.sql`). **Backup before any live
  restore.**
- **Schedule:** `scripts/backup-cron.example` chains `backup-db.sh &&
  verify-backup.sh` nightly, adds a weekly PITR base backup and a monthly
  verify-from-the-oldest-backup drill. A monitor (healthchecks.io / cron mail)
  on the job's exit code is the backup-failure alert counted in §8.
- **Point-in-time recovery (opt-in):** `docker compose -f compose.yaml
  -f compose.pitr.yaml` turns `db` into a WAL-archiving primary (streaming
  `archive_command` → `./wal-archive`). Take a base backup
  (`./scripts/pitr-basebackup.sh`; weekly suffices alongside continuous
  archiving), then recover to any instant with
  `PITR_TARGET="…" ./scripts/pitr-restore.sh` — it replays into a **throwaway
  container on :5433**, never over the live DB. Ship `./wal-archive` off-host or
  it buys nothing. For production prefer **pgBackRest**
  (`pgbackrest.conf.example`): encryption, retention and incrementals built in.
- Verified this release: 16 kB dump → restore preserved 1 game + 2 moves (QA-025).

## 5. Migrations as a controlled deployment step (REL-006)

Migrations run **before** the new code serves traffic, as an explicit step:

- Compose: the `api` service command is `alembic upgrade head && uvicorn …`
  (`compose.yaml`), so a container never serves on a stale schema.
- The `api` image ships `alembic/` + `alembic.ini` (`apps/api/Dockerfile`).
- CI proves the model↔schema contract stays in lockstep: `alembic upgrade head`
  then `alembic check` (`.github/workflows/ci.yml`) — a model change with no
  migration fails the build.
- **Rollout rule:** expand/contract — add columns nullable, backfill, then
  enforce. Never drop/rename in the same release that needs the new code.
- **Rollback a migration:** `alembic downgrade -1` (each migration has a tested
  `downgrade`); for destructive changes, restore from the last backup instead.

## 6. Health checks (REL-007)

- `GET /api/v1/health` — liveness: returns `{"status":"ok"}` if the process is up.
- `GET /api/v1/ready` — readiness: `{"status":"ready"}` only if the DB answers
  `SELECT 1`; otherwise `{"status":"not-ready"}` (used by the load balancer to
  hold traffic until the DB is reachable).
- Compose `api.healthcheck` polls `/health`; `db` uses `pg_isready`. The `api`
  waits for `db: condition: service_healthy`.

## 7. Structured logs (REL-008, MON-001)

- One record per line to **stdout** (`app/core/telemetry.py`). Default is
  **JSON**: `{"ts", "level", "logger", "msg", "request_id"?, "http"?, "exc"?}`.
  `LOG_JSON=false` restores the
  `%(asctime)s %(levelname)s [%(name)s] %(message)s` text format.
- Every HTTP request gets a **request id** (an inbound `X-Request-ID` is
  honored, else one is generated), echoed on the response and carried by every
  log line the request produces — trace a slow review with one id.
- Health/scrape paths (`/health`, `/ready`, `/metrics`) are kept out of the
  access log so polling does not bury real lines.
- Level via `LOG_LEVEL` (`INFO` default). No secrets or session tokens are
  logged — the access formatter whitelists method/path/status/duration only;
  auth errors return opaque messages (QA-019).

## 8. Monitoring & error reporting (REL-009, D14 — wired in Phase 12A)

- **`GET /metrics`** (Prometheus text format, api container port 8000) via
  `prometheus-fastapi-instrumentator`: per-route request rate/latency/error
  code families (`http_requests_total`, `http_request_duration_seconds`).
  It is deliberately **not** proxied through `web` and not part of the
  OpenAPI contract — scrape the api port internally.
- **Bespoke instruments** (`app/core/telemetry.py`) for what actually hurts:
  | Metric | Meaning |
  |--------|---------|
  | `engine_analyse_seconds{provider}` | engine batch wall time, labeled `stockfish` / `stockfish-cloud` — sizes TD-013/ANL-008 |
  | `engine_unavailable_total` | D7 outages (no binary and no key, or a dead engine mid-call); review failures count here even though the HTTP answer is 200-with-status-failed |
  | `rate_limit_rejections_total{bucket}` | 429s per limiter (auth/moves/assistant/review/training) — a spike on `auth` is the cheapest brute-force alarm |
  | `cloud_units_used_today` | hosted units drawn from the shared daily pot (RL-003) |
  | `cloud_upstream_errors_total{status}` | upstream 4xx by code — `402`/`429` means plan trouble |
  | `ws_connections_active` | live sockets in the single-replica hub (TD-012 visibility) |
- **Alert targets:** `/ready` failing (DB down), sustained 5xx,
  `engine_unavailable_total` rising, `cloud_units_used_today` near its budget,
  `rate_limit_rejections_total{bucket="auth"}` spikes, backup-job failures.
- **Error reporting:** FastAPI's default 500 handler logs the traceback server-side
  and returns a generic `{"detail":"Internal server error"}` to clients (no stack
  traces leak). Hook an APM (Sentry/OTel) at `app/main.py` if desired — the seam
  exists; the JSON logs + `/metrics` already carry the load (deferred by D14).

## 9. Production dependency install (REL-010)

- `pip install .` builds a clean wheel from `pyproject.toml` (verified: builds
  `chess_engine_api-0.1.0-py3-none-any.whl`, 32 kB). Runtime deps are pinned with
  `>=` floors; the `dev` extra (pytest/ruff/mypy) is **not** installed in prod.
- Frontend: `npm ci` (lockfile-exact) → `npm run build` produces `dist/` served by
  nginx. Dependency vulnerabilities are scanned with `pip-audit` + `npm audit`
  (QA-018, both clean this release).

## 10. Stockfish deployment & licensing (REL-011)

- The Stockfish **binary is not committed or vendored** in this repo — it is
  **GPL-3.0**, and adding it to the source tree would impose GPL on the whole
  service (`app/engine/stockfish.py`).
- **Both container images install it from the distro at build time**
  (`apt-get install stockfish` in `apps/api/Dockerfile` and `Dockerfile.dev`),
  because the computer opponent and game review are real Stockfish now
  (PLAY-001 / decision D7). Installing it into an image you run yourself is an
  install; **publishing that image is redistribution of the binary** — review
  GPL-3.0 obligations (source availability, SBOM) before doing so (TD-004).
- Discovery order: explicit `STOCKFISH_PATH`, then `PATH`, then the distro
  package locations the adapter probes. Debian/Ubuntu install to
  `/usr/games/stockfish`, which slim images keep off `PATH`, so the probe is
  what makes the shipped image work with no configuration.
- **Local-first, hosted fallback.** `app/engine/factory.py` decides once per call:
  if a binary resolves (`STOCKFISH_PATH`, then `PATH`, then the distro probe),
  use `StockfishProvider`; otherwise use `CloudStockfishProvider` with
  `STOCKFISH_API_KEY`. If neither is available it raises one error naming both
  fixes (install/set the binary, or set the key). `compose.yaml` and
  `compose.dev.yaml` forward `STOCKFISH_API_KEY` / `STOCKFISH_API_BASE_URL` into
  the api container; running `uvicorn` on the host reads `apps/api/.env`
  (pydantic-settings loads it relative to the cwd), so mirror the key there too.
- The hosted score's side-to-move perspective is not documented upstream, so the
  provider calibrates it once at runtime (a Black-to-move, queen-up probe) and
  caches the convention process-wide; the probe falling back to the UCI mover-POV
  default keeps reviews correct rather than silently sign-flipped. The provider
  clamps to the plan's max depth and never echoes the key or raw body in errors.
- With no binary **and** no key, engine moves and reviews fail cleanly (503) — there is
  **no silent fallback to the weaker custom engine** (D7). Local hot-seat and
  online human-vs-human play are unaffected; only computer games need it.
- Alternative installs: build from
  <https://github.com/official-stockfish/Stockfish>, or on macOS
  `brew install stockfish` when running `uvicorn` on the host rather than in
  Docker (a host run needs a host binary).

## 11. CORS & cookie settings (REL-012)

- `CORS_ORIGINS` is an explicit allowlist (comma-separated) — never `*` when
  credentials are allowed. `allow_credentials=True` is set in `app/main.py`.
- `COOKIE_SECURE=true` in production so the session cookie is sent only over HTTPS.
  Verified in the production smoke run (register → play → engine reply, cookies
  first-party under TLS).

## 12. Production smoke tests (REL-013)

- `./scripts/smoke-prod.sh` (point `API_BASE` at the deployed host) runs the full
  loop: `health` → `register` → `create game` → submit `e2e4` → engine replies
  (version 3). Exits non-zero on any unexpected status. Run it as the final gate
  after deploy/rollback.

## 13. Rollback procedures (REL-014)

- **App rollback:** redeploy the previous image tag; Compose `restart:
  unless-stopped` + the healthcheck gate the swap. Schema must be
  backward-compatible (expand/contract, §5) so old code runs on the new schema.
- **Data rollback:** take a fresh backup, then `./scripts/restore-db.sh <backup.dump>`
  into a scratch DB, verify row counts, and only then restore live.
- **Order:** app rollback first (fast, reversible); data restore only if the
  migration corrupted data. Always backup before any live restore.

## 14. Release notes & final status (REL-015..017)

- **Version:** API `0.1.0` (`pyproject.toml`, `apps/web/package.json`). Tag
  releases `v0.1.0` on `main` after all gates are green.
- **This release ships:** rules engine + custom AI (Phases 1/6), Postgres schema
  (Phase 2), auth/sessions (Phase 3), games API (Phase 4), React client (Phase 5),
  Stockfish adapter + benchmarks (Phase 7), QA sweep (Phase 8), and this deploy
  surface (Phase 9).
- **Final status:** see `PROJECT_CHECKLIST.md` Summary — all P0/P1 items complete;
  QA-026 release sign-off is recorded there. Deferred P2/P3 items (analysis UX,
  extra benchmark suites, APM) are listed, not blocking.

