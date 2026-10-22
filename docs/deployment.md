# Deployment & Operations (Phase 9, REL-001..017)

> How to ship this project: production config, secrets, HTTPS, backups,
> migrations, health checks, logging, monitoring, Stockfish licensing, CORS,
> smoke tests, rollback, and release notes.

## 1. Production configuration (REL-001)

| Setting | Source | Production value |
|---------|--------|------------------|
| `APP_ENV` | env | `production` |
| `SECRET_KEY` | env/secret store | unique ≥32 random chars (app refuses to start without it, REL-002); HMAC key for recovery-token derivation |
| `DATABASE_URL` / `database_url` | env | managed Postgres DSN (psycopg URL) |
| `CORS_ORIGINS` | env | exact public origin(s), e.g. `https://chess.example.com` (REL-012) |
| `COOKIE_SECURE` | env | `true` **only** with TLS termination; the Compose default is `false` because nginx serves plain HTTP locally (REL-012) |
| `LOG_LEVEL` | env | `INFO` (or `WARNING`) |
| `ENGINE_BACKEND` | env | `stockfish_remote` (the sidecar; Compose default), `stockfish_local` (host binary for dev), or `custom` (in-process fallback) |
| `ENGINE_BASE_URL` | env | `http://engine:8050` — the sidecar on the private `engine` network (never host-published) |
| `STOCKFISH_PATH` | env | absolute path or empty (PATH lookup), **`stockfish_local` only**; never from clients |
| `FORWARDED_ALLOW_IPS` | env | CIDR/hosts allowed to set `X-Forwarded-For`; Compose default `172.16.0.0/12` (the nginx bridge). Empty = trust the socket peer only |
| `PUBLIC_WEB_BASE_URL` | env | public origin used to build clickable recovery links in emails (falls back to the request base URL) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_FROM` | env/secret store | recovery email delivery; **unset ⇒ `ConsoleEmailSender`** (logs the link so dev needs zero config). The factory selects SMTP the moment `SMTP_HOST` is set |

Copy `.env.example` → `.env` for local dev only. **Never commit `.env`.**
All of the above are declared on the `Settings` model and mirrored in
`.env.example` — there is no drift between advertised and actual settings.

### Service topology

Compose runs five logical services: `web` (nginx-unprivileged, non-root, listens
8080), `api` (FastAPI, non-root), `db` (Postgres, **no published port**),
`migrate` (one-shot `alembic upgrade head`), and `engine` (Stockfish sidecar,
**no published port**). Every image runs as a non-root `USER` and is CPU/memory
bounded. `db` sits on the private `backend` network; `engine` on an
`internal: true` network with no egress, so the sidecar is reachable only by the
API (its sole access control — no auth, no DB) and Stockfish stays out of the API
image (REL-011 / ADR-006).

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
4. Emit `Strict-Transport-Security` at the TLS edge. The container's nginx ships
   `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`,
   `Referrer-Policy`, and `Permissions-Policy` unconditionally (`apps/web/nginx.conf`),
   but **HSTS is added at the TLS edge, not in this file**, so it is never sent
   over plain HTTP.
5. Verify: `curl -sI http://<host>` → `301`; `https://<host>` → `200` with the
   security headers above.

## 4. Backups & restoration (REL-004/REL-005)

- **Backup:** `./scripts/backup-db.sh` — timestamped `pg_dump` into `./backups/`,
  keeps the newest 14 (`BACKUP_KEEP`). Schedule nightly via cron/scheduler.
- **Restore:** `./scripts/restore-db.sh <backup.sql> [target_db]` — creates the
  target, loads the dump, prints row counts. **Backup before restoring live.**
- Verified this release: 16 kB dump → restore preserved 1 game + 2 moves (QA-025).

## 5. Migrations as a controlled deployment step (REL-006)

Migrations run **before** the new code serves traffic, as an explicit one-shot
step decoupled from the serving process:

- Compose: a dedicated `migrate` service runs `alembic upgrade head`
  (`restart: "no"`) and `api` starts only via
  `depends_on: migrate: condition: service_completed_successfully` — so a
  container never serves on a stale schema and no serve command mixes in a
  migration (`compose.yaml`).
- The `api` image ships `alembic/` + `alembic.ini` (`apps/api/Dockerfile`), which
  the `migrate` service reuses.
- CI proves the model↔schema contract stays in lockstep: `alembic upgrade head`
  then `alembic check` (`.github/workflows/ci.yml`) — a model change with no
  migration fails the build.
- **Rollout rule:** expand/contract — add columns nullable, backfill, then
  enforce. Never drop/rename in the same release that needs the new code.
- **Rollback a migration:** `alembic downgrade -1` (each migration has a tested
  `downgrade`); for destructive changes, restore from the last backup instead.

## 6. Health checks (REL-007)

- `GET /api/v1/health` — liveness: returns `{"status":"ok"}` if the process is up.
- `GET /api/v1/ready` — readiness gate for the load balancer: **`200`** when the DB
  answers `SELECT 1`, **`503`** when it does not (a `200` with a `not-ready` body
  would be useless to a proxy). Body `{status, database, engine}`. The `engine`
  field reports the opponent backend (`builtin`/`local`/`up`/`degraded`) and is
  **informational only** — an unreachable sidecar degrades the opponent to the
  in-process fallback but never flips readiness to `503`; only the DB does.
- Compose: `api.healthcheck` polls `/health`; `db` uses `pg_isready`; the `engine`
  sidecar exposes `/healthz` (UCI `uciok`) and `api` waits on
  `engine: condition: service_healthy` plus `migrate: ...service_completed_successfully`.

## 7. Structured logs (REL-008)

- Logs are **structured JSON**, one object per line on **stdout**, installed by
  `configure_logging()` in `app/core/observability.py` (`JsonLogFormatter`). Each
  record carries `ts`, `level`, `logger`, `message`, and a `request_id`.
- **Request correlation:** `app/main.py` middleware mints (or reuses a trusted
  proxy's) 8-hex `X-Request-ID`, stores it in a `ContextVar` so every log line
  from one request shares it, and echoes it on the response.
- Level via `LOG_LEVEL` (`INFO` default). The formatter emits only standard
  record fields plus explicit `extra` keys and **never** logs session tokens,
  passwords, or request bodies; auth errors return opaque messages (QA-019).

## 8. Monitoring & error reporting (REL-009)

- **Metrics to wire** (P2, pluggable): request rate/latency/error rate on the API,
  engine-move latency, and 5xx rate — exported via stdout and scraped by the host.
- **Alerting targets:** `/ready` failing (DB down), sustained 5xx, engine-move
  timeouts (503s), backup-job failures.
- **Error reporting:** FastAPI's default 500 handler logs the traceback server-side
  and returns a generic `{"detail":"Internal server error"}` to clients (no stack
  traces leak). Hook an APM (Sentry/OTel) at `app/main.py` if desired — out of
  scope for this repo but the seam exists.

## 9. Production dependency install (REL-010)

- `pip install .` builds a clean wheel from `pyproject.toml` (verified: builds
  `chess_engine_api-0.1.0-py3-none-any.whl`, 32 kB). Runtime deps are pinned with
  `>=` floors; the `dev` extra (pytest/ruff/mypy) is **not** installed in prod.
- Frontend: `npm ci` (lockfile-exact) → `npm run build` produces `dist/` served by
  nginx. Dependency vulnerabilities are scanned with `pip-audit` + `npm audit`
  (QA-018, both clean this release).

## 10. Stockfish sidecar & licensing (REL-011 / ADR-006)

- **Topology:** Stockfish ships as a **separate container** (`services/stockfish`)
  on an `internal: true` Docker network with **no published port** and no
  internet egress. The API's `RemoteStockfishProvider` (httpx, 3 s connect / 8 s
  read) is its only client; the sidecar never mounts the DB and never imports
  `app.*`. It holds **one persistent** `popen_uci` engine per worker, guarded by
  a `MAX_CONCURRENT_SEARCHES` semaphore (the warm pool ADR-006 describes), and
  re-applies the hard bounds **server-side** (`depth ≤ 15`, `time ≤ 1000 ms`,
  review `25`/`5000`) so a hostile client cannot request an unbounded search.
- **Licensing:** the binary is **GPL-3.0** and is **not** baked into the API
  image — the API image stays binary-free, keeping GPL outside it. The sidecar
  installs the unmodified distro package (`apt-get install stockfish`, Ubuntu
  `stockfish 16`; provenance in `app/engine/stockfish.py`); review GPL-3.0 source-
  availability obligations before redistributing that image as a product.
- **Degradation:** with `ENGINE_BACKEND=stockfish_remote` and the sidecar down,
  `circuit.py` falls back to the in-process `CustomEngineProvider` after N
  consecutive `EngineUnavailableError` — so the bot keeps moving and the API
  never 500s (it may 503 only if even the fallback fails). Use
  `ENGINE_BACKEND=stockfish_local` + `STOCKFISH_PATH` for non-Docker dev.

## 11. CORS & cookie settings (REL-012)

- `CORS_ORIGINS` is an explicit allowlist (comma-separated) — never `*` when
  credentials are allowed. `allow_credentials=True` is set in `app/main.py`.
- `COOKIE_SECURE=true` sends the session cookie only over HTTPS. The Compose
  default is `false` because local nginx serves plain HTTP; **set it `true` only
  once TLS is terminated at the edge**, and pair that with exact `CORS_ORIGINS`.

## 12. Production smoke tests (REL-013)

- `./scripts/smoke-prod.sh` (point `API_BASE` at the deployed host) runs the full
  loop and asserts each step: `health` → `register` → create a **computer** game
  (`player_color`/`engine_level`) → submit `e2e4` and confirm the **engine
  auto-reply** lands in the same response → **resign** and check the recorded
  **result/winner** → download **PGN** → and probe **`/ready`**. Exits non-zero on
  any unexpected status. Run it as the final gate after deploy/rollback.

## 13. Rollback procedures (REL-014)

- **App rollback:** redeploy the previous image tag; Compose `restart:
  unless-stopped` + the healthcheck gate the swap. Schema must be
  backward-compatible (expand/contract, §5) so old code runs on the new schema.
- **Data rollback:** take a fresh backup, then `./scripts/restore-db.sh <backup.sql>`
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

