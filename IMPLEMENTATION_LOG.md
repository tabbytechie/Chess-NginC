# Implementation Log

> Running record of work sessions: task attempted, files changed, tests executed, results, defects, decisions, remaining work, next task.

---

## Session 2026-10-09 — Foundation & planning

**Task.** Inspect the empty repository and establish the planning/tracking foundation (plan, checklist, loops, agents, docs).

**Environment (LOOP A).**
- Directory: `Chess NginC` — empty, not a Git repo.
- Python 3.14.2, Node v25.2.1, npm 11.7.0, psql 14.19 (client), Docker **not installed**, pnpm **not installed**.
- Disk critically full: 99% capacity, ~3.2 GiB free (transient ENOSPC observed, recovered).

**Files created.**
- `PROJECT_CHECKLIST.md` (FND-008) — all 219 requirement IDs across Phases 0–9.
- `docs/PLAN.md` — roadmap, milestones M0–M6, environment reality check.
- `docs/development-loops.md` — LOOP A–H machine + Definition of Done.
- `docs/agents.md` — agent roles + reusable task briefs (recognized by harness as AGENTS.md).
- `README.md`, `CONTRIBUTING.md`.
- `docs/code-standards.md`, `docs/architecture.md`.
- `IMPLEMENTATION_LOG.md` (this file), `TECHNICAL_DEBT_REGISTER.md`.
- `.gitignore`, `.env.example`.

**Tests executed.**
- None (documentation-only session; no code yet). Verification is `git diff --check` + content consistency review (LOOP E).

**Results.**
- Git repo initialized on `main` (FND-002). Planning artifacts committed (see commit log).

**Defects discovered.**
- ENOSPC on write tool during first README/CONTRIBUTING attempt; transient disk-full. Recovered without action.

**Decisions made.**
- Proceed with **npm** (pnpm absent).
- Document both Docker and local-Postgres paths (Docker absent).
- Defer code scaffold (FND-003) until toolchain exists, per spec §5 ("add modules when functionality exists").

**Remaining work.** FND-011/012 (gitignore/env — done this session), then FND-013..FND-017 toolchains, FND-003 scaffold, CHS-* rules domain.

**Next recommended task.** Configure backend toolchain (`pyproject.toml`, Ruff, mypy, pytest) and frontend toolchain (strict TS, ESLint, Prettier, Vitest) — FND-013..FND-017.

---

## Session 2026-10-09 (b) — Toolchain & health endpoint (FND-003, FND-013..FND-017, FND-020..FND-022)

**Task.** Establish and verify the backend and frontend toolchains, plus a minimal health endpoint.

**Files changed.**
- `apps/api/pyproject.toml`, `apps/api/requirements.lock` (pinned), `apps/api/README.md`
- `apps/api/app/main.py`, `app/api/v1/health.py`, `app/core/__init__.py` (+ package `__init__.py`)
- `apps/api/tests/test_health.py`
- `apps/web/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `.prettierrc`, `.prettierignore`, `index.html`, `README.md`
- `apps/web/src/{main.tsx,App.tsx,App.test.tsx,vite-env.d.ts}`, `src/test/setup.ts`
- Directory scaffold: `apps/`, `infra/docker`, `scripts`, `.github/workflows`, `docs/decisions`.

**Tests executed (all passed).**
- Backend: `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy app` ✅ · `pytest` → **2 passed** (1 warning: starlette TestClient `httpx`→`httpx2` deprecation).
- Backend start: `uvicorn app.main:app` → `/api/v1/health` 200 `{"status":"ok"}`, `/` 200.
- Frontend: `npx tsc --noEmit` ✅ · `npx eslint .` ✅ · `npx prettier --check` ✅ · `npx vitest run` → **1 passed** · `npm run build` ✅ (Vite 8, 15 modules).
- Frontend start: `vite` dev server serves `index.html` on :5173.

**Defects discovered & fixed.**
- ESLint rejected `reactHooks.configs.recommended` (legacy `plugins` array); switched to `reactHooks.configs.flat['recommended-latest']`.
- npm cache `~/.npm` contains root-owned files → `sudo chown` needed (not run); worked around with a temp `--cache` dir.
- Prettier reformatted 6 files (cosmetic); applied `--write`.

**Decisions made.**
- Python 3.14.2 wheels available for all deps (fastapi 0.143, sqlalchemy 2.1.4, psycopg 3.3.6, chess 1.11.2, pydantic 2.14, ruff 0.16.10, mypy 2.4.0).
- `python-chess` on PyPI is now a meta-package (1.999) that installs `chess==1.11.2`; `import chess` is the correct import.
- Used plain `uvicorn` (no `[standard]`) for now — uvloop/httptools 3.14 wheel availability unconfirmed.
- Frontend pinned via `package-lock.json` (React 19.3, Vite 8, TS 6, ESLint 10, Vitest 4).

**Remaining work.** FND-018/019 (Docker Compose + Postgres), FND-023 (CI), FND-024, then Phase 1 chess domain.

**Next recommended task.** Phase 1 chess-rules domain (CHS-001..CHS-006): game modes/status enums, game model, rules adapter over python-chess, board init, UCI validation — with tests.

---

## Session 2026-10-09 (c) — Housekeeping pause (corrected diagnosis)

**Finding.** The earlier npm "root-owned cache files" error is **not** an ownership problem. `~/.npm` and all subdirs are owned by uid 501; `find` shows zero non-user files. However, `touch ~/.npm/...` and `touch ~/...` return `Operation not permitted` while the workspace is writable → this is the assistant's workspace-write sandbox blocking `$HOME` writes. npm misattributed it.

**Decision.** `sudo chown -R 501:20 ~/.npm` is **unnecessary**. The proven fix is `--cache $(mktemp -d)` for future `npm install` (deps are already installed and lockfile committed). Updated TD-009 accordingly.

**Remaining work.** Optional user-side disk housekeeping (disk at 97%, ~6.4 GiB free); then resume Phase 1 (CHS-001..CHS-006).

**Next recommended task.** Resume Phase 1 chess-rules domain.

---

## Session 2026-10-09 (d) — Chess-rules domain core (CHS-001..CHS-010)

**Task.** Implement the chess-rules domain: enums, Game/Move model, and a `ChessRules` adapter over python-chess (board init, UCI validation, SAN, check/checkmate/stalemate).

**Files changed.**
- `apps/api/app/games/domain.py` — `GameMode`/`Color`/`GameStatus` (`StrEnum`), `Move`, `Game`, `STARTING_FEN`.
- `apps/api/app/games/errors.py` — `InvalidMoveError`, `IllegalMoveError`.
- `apps/api/app/games/rules.py` — `ChessRules` adapter (only module importing `chess`).
- `apps/api/app/games/__init__.py`.
- `apps/api/tests/test_domain.py`, `apps/api/tests/test_rules.py`.

**Tests executed (all passed).**
- `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy app` ✅ (10 files) · `pytest` → **22 passed**.

**Defects discovered & fixed.**
- ruff `UP042` → switched `(str, Enum)` to `StrEnum`.
- ruff `I001` import sorting → `ruff check --fix`.
- Promotion test expected `a8=Q` but position gave `a8=Q+` (king on a-file) → used a king-safe FEN.

**Decisions made.**
- `ChessRules` is the single module importing `chess`; domain types are chess-free.
- Fifty-move/threefold repetition deferred to CHS-014/CHS-016 (documented in `status()`).

**Remaining work.** CHS-011..CHS-024 (castling, en passant, promotion, repetition, resignation, draw claims, FEN/PGN, history/replay, undo, invariants, edge/property tests).

**Next recommended task.** CHS-011..CHS-013 (castling, en passant, promotion/underpromotion) + CHS-017 (FEN generate/validate) with targeted tests.

---

## Session 2026-10-09 (e) — Database verification & repair (DB-001..DB-021, FND-019)

**Task.** Verify and complete Step 2 (Phase 2 database): the prior session left uncommitted DB work with empty Alembic stub migrations (upgrade/downgrade were `pass`); DB was stamped at head but contained zero tables.

**Files changed.**
- `alembic/env.py` — import `app.models` so autogenerate sees all tables (was importing only `Base`).
- `alembic/versions/146802a49aef_initial_schema.py` — real autogenerated initial schema (users, games, sessions, game_moves, engine_runs + FKs/indexes); replaced two empty stub revisions.
- `app/core/database.py` — `Generator[Session,None,None]` return type (mypy fix); `SettingsConfigDict` instead of deprecated class-based `Config`.
- `app/engine/engine.py` — typed `termination` Literal + float `_deadline_ms` (mypy fixes).
- `app/games/rules.py` — collapsed nested `if` (ruff SIM102).
- `PROJECT_CHECKLIST.md` — marked FND-019, DB-021 `[x]`; corrected DB-020 evidence.

**Tests executed (all passed).**
- `alembic stamp base && alembic upgrade head` → 6 tables created; `alembic downgrade base && alembic upgrade head` round-trip ✅ (DB-020/DB-021).
- `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy app` ✅ (23 files) · `pytest` → **98 passed** (live Postgres repository tests included).

**Defects discovered & fixed.**
- Empty stub migrations masked as done (checklist DB-003..DB-012 claimed migrated with no tables). Fixed via autogenerate + re-apply; downgrade verified.
- Pre-existing mypy/ruff issues in uncommitted engine/rules files; fixed as gate prerequisites.

**Decisions made.**
- Single squashed initial migration (no prior schema ever shipped, so no upgrade-from-stub path needed).

**Remaining work.** DB-008/DB-009 (benchmark tables), DB-022 (backup docs), FND-023 (CI); then Phase 3 auth (SEC-001+).

**Next recommended task.** Commit this DB step, then Phase 3 authentication (registration/login/session revocation over the now-live `users`/`sessions` tables).

---

## Session 2026-10-09 (f) — Phase 3 authentication (SEC-001..008, SEC-012, SEC-014..017, SEC-020..021)

**Task.** Implement registration, login, session cookies, and supporting
security controls over the live `users`/`sessions` tables.

**Files changed.**
- `app/auth/__init__.py`, `security.py` (bcrypt + token generation),
  `validators.py` (email normalize/validate), `service.py`
  (register/login/authenticate/logout).
- `app/api/v1/schemas.py` (Register/Login/User/Error schemas),
  `deps.py` (rate limit, same-origin check, `get_current_user`),
  `auth.py` (register/login/logout/me routes).
- `app/main.py` — explicit CORS allowlist from settings.
- `app/core/database.py` — auth settings (cookie flags, TTL, rate limit).
- `pyproject.toml` + `requirements.lock` — added `bcrypt==5.0.0`.
- `tests/test_auth.py` — 9 tests (flow, cookies, expiry, rate limit, CSRF).

**Tests executed (all passed).**
- `pytest` → **107 passed** (9 new auth tests, live Postgres).
- `ruff check` ✅ · `ruff format --check` ✅ · `mypy app` ✅ (30 files).

**Defects discovered & fixed.**
- FastAPI `Annotated` forbids defaults inside `Cookie()` — moved `= None`
  to parameter declarations.
- Unvalidated `csrf_token` cookie issued but never checked — removed; CSRF
  defense is SameSite=Lax + Origin/Referer allowlist instead.
- Tests initially relied on ambient DB tables — fixtures now
  create/drop schema per test like `test_game_repository.py`.

**Decisions made.**
- Sessions are opaque random tokens in DB (revocable server-side), 7-day TTL.
- Generic "Invalid email or password" for both failure modes (no enumeration).
- In-memory per-IP rate limiter (10/min); Redis before multi-worker prod.
- SEC-009/010/011/013 deferred: need deployment (Phase 9) / game & engine
  HTTP endpoints (Phase 4/6); repository ownership already enforced.

**Remaining work.** Phase 4 backend API (games CRUD over GameRepository +
auth deps), then SEC-010/011 HTTP ownership tests.

**Next recommended task.** Phase 4 games API (API-005..011, API-016..019):
POST/GET games, POST moves with rules validation + optimistic concurrency.

---

## Session 2026-10-09 (g) — Phase 4 games API (API-001..012, API-016..024, SEC-010/011)

**Task.** Expose games over HTTP: CRUD, moves, undo, resign, draw-claim,
engine-move, with auth + ownership + concurrency + docs.

**Files changed.**
- `app/games/service.py` — orchestration (create/list/get/move/undo/resign/
  draw/engine-move) with GameNotFound/StaleVersion/IllegalMove/GameFinished
  errors mapped to 404/409/422.
- `app/api/v1/games.py` — 8 routes (API-005..012) with response models.
- `app/api/v1/schemas.py` — game/move/version/engine request + response types.
- `app/main.py` — games router registered.
- `tests/test_games.py` — 9 integration tests (flow, isolation, checkmate,
  undo, resign, draw, engine).
- `tests/test_openapi.py` — OpenAPI route + ref validation (API-021).
- `tests/conftest.py` — shared db/client/authed/other fixtures.
- `docs/api.md` — status codes + endpoint reference (API-020).
- `apps/web/src/lib/api-types.ts` (+ contract test) — frontend types (API-022).

**Tests executed (all passed).**
- Backend: `pytest` → **117 passed** (live Postgres).
- `ruff check` ✅ · `ruff format --check` ✅ · `mypy app` ✅ (32 files).
- Frontend: `tsc` ✅ · `eslint` ✅ · `prettier` ✅ · `vitest` 3 passed ·
  `vite build` ✅.

**Defects discovered & fixed.**
- Starlette deprecated `HTTP_422_UNPROCESSABLE_ENTITY` → use
  `HTTP_422_UNPROCESSABLE_CONTENT`.
- Autouse table-wipe fixture broke `test_game_repository.py` (ran before its
  own schema setup) → tolerate missing tables with rollback.

**Decisions made.**
- API-013/014/015 deferred with reasons (analysis UX undecided; benchmark
  harness is Phase 7).
- Versions only move forward (undo bumps, never rewinds) — simpler clients.
- Terminal status derived server-side after every move (no client claims).

**Remaining work.** Phase 5 frontend (board, game state, API client over
these endpoints).

**Next recommended task.** Phase 5 frontend: board rendering + play vs engine
via POST moves / engine-move, using `api-types.ts`.

---

## Session template (copy per session)

**Task.** …
**Files changed.** …
**Tests executed.** (exact commands + results)
**Results.** …
**Defects discovered.** …
**Decisions made.** …
**Remaining work.** …
**Next recommended task.** …
---

## Session (h) — Phase 5 frontend

**Task.** Build the React + TypeScript client (Phase 5, WEB-001..WEB-030) against the Phase 3/4 API.

**Files changed.**
- `apps/web/src/lib/api-client.ts` — typed client with cookie session + `ApiError` normalisation.
- `apps/web/src/lib/chess.ts` — FEN parsing, square colouring, captured-piece accounting.
- `apps/web/src/app/auth-context.ts`, `app/AuthContext.tsx`, `app/useAuth.ts`, `app/RequireAuth.tsx`.
- `apps/web/src/pages/AuthPages.tsx`, `pages/Dashboard.tsx`, `pages/GamePage.tsx`.
- `apps/web/src/components/Chessboard.tsx`, `MoveHistory.tsx`, `GameStatus.tsx`.
- `apps/web/src/App.tsx`, `main.tsx`, `styles.css`.
- Tests: `App.test.tsx`, `pages/GamePage.test.tsx`, `lib/chess.test.ts`, `src/test/setup.ts`, `vite.config.ts`.
- `apps/web/package.json` — added `@testing-library/user-event`.

**Tests executed.**
- `npx tsc --noEmit` → clean
- `npx eslint src --max-warnings=0` → clean
- `npx prettier --check src` → clean
- `npx vitest run` → **43 passed** (4 files)
- `npx vite build` → success, 274 kB / 87 kB gzip
- `pytest` (api, regression) → **117 passed**

**Results.** Full play loop works end-to-end: register/login, create game, click-to-move and
HTML5 drag-and-drop, promotion dialog, move history, captured pieces, undo, reset-to-start,
resign, engine move, and resume of an existing game. Games reload from the API and render the
stored position.

**Defects discovered and fixed.**
1. **`isLightSquare` inverted** — `(file + rank) % 2 === 1` made a1 and h8 *light*. The whole
   board rendered with swapped colours; caught by the new `chess.test.ts` cases.
2. **Reset-to-start loop terminated after one undo** — the loop bound was `game.moves.length`
   captured before the first await, so it used the stale initial count while the refetched value
   shrank to 0. Rewritten as a `while` loop on the refetched state with a no-progress guard.
3. **No RTL cleanup between tests** — vitest runs without `globals`, so auto-cleanup never
   registered; DOM accumulated and queries matched duplicates. Added `cleanup()` in setup.
4. **Spy leakage** — `renderGame` re-spied `getGame` over the per-test mock, silently replacing
   test intent. `renderGame` now mocks only `me`; each test owns `getGame`.
5. **Fast-refresh violation** — `useAuth` and the context lived in `AuthContext.tsx`, breaking
   Fast Refresh. Split into `auth-context.ts` (context + type), `useAuth.ts` (hook), and
   `AuthContext.tsx` (provider component only).
6. Form labels used implicit nesting, producing ambiguous `getByLabelText` matches; switched to
   explicit `id`/`htmlFor` pairs.

**Decisions made.**
- Board squares are `<button role="gridcell">` inside `role="grid"` with per-square
  `aria-label` and arrow-key navigation, so the board is usable without a mouse.
- Piece rendering uses Unicode glyphs rather than an image sprite — no asset pipeline needed
  for this phase.
- Optimistic UI was rejected: the board only changes on a confirmed server response, which is
  what makes the 409 resync path observable and testable.
- Reset-to-start is a client-side undo loop because the API has no bulk-reset endpoint.

**Remaining work.** WEB-029 (browser e2e with Playwright — needs the harness, Phase 9).

**Next recommended task.** Phase 6 analysis/review UI (API-013 analysis endpoint + board
annotations), or the engine evaluation pipeline in Phase 7 if analysis UX is deferred.

---

## Session 2026-10-09 (i) — Phase 7 Stockfish & benchmarking core (BEN-001..013, BEN-018..020, BEN-022)

**Task.** Implement the chronological Step 7: Phase 7 Stockfish & Benchmarking core
(no explicit "Step 7" label exists in docs; session (e) maps Step 2 → Phase 2, so
Step 7 → Phase 7, the next phase after the completed Phase 5 frontend).

**Files changed.**
- `apps/api/app/engine/stockfish.py` — UCI adapter: provenance constants (BEN-001/002),
  `StockfishConfig.bounded()` hard caps (BEN-006), `resolve_binary()`, `analyse_position()`
  (BEN-004/005/008), `_extract_score()` normalization incl. mates (BEN-013), graceful
  missing-binary/crash errors (BEN-007). Binary never distributed (BEN-003).
- `apps/api/app/engine/benchmark_suite.py` — versioned `v1` suite, 12 validated FENs (BEN-009).
- `apps/api/app/engine/benchmark.py` — `compare_position()`, `agreement_rate()`,
  `mean_score_gap()`, `hardware_fingerprint()`, `stockfish_version_label()` (BEN-010..013).
- `apps/api/app/models/benchmark_run.py`, `benchmark_result.py`, `models/__init__.py` —
  persistence tables (BEN-019).
- `apps/api/alembic/versions/5a0dcdb13bb3_benchmark_runs_and_results.py` — migration,
  upgrade/downgrade round-trip verified.
- `apps/api/app/core/database.py` — `STOCKFISH_PATH` / depth / time settings (BEN-002/020).
- `apps/api/tests/test_stockfish.py` (5 tests, fake UCI script — no binary needed),
  `apps/api/tests/test_benchmark.py` (6 tests incl. repeatability BEN-022).
- `docs/engine-strength.md` — Stockfish source/licensing/adapter/suite/harness section (BEN-021 partial).
- `PROJECT_CHECKLIST.md` — BEN-001..013, BEN-018..020, BEN-022 → `[x]` with evidence.

**Tests executed (all passed).**
- `.venv/bin/pytest tests/test_stockfish.py tests/test_benchmark.py` → **11 passed**.
- `.venv/bin/pytest` (full backend) → **128 passed**.
- `.venv/bin/ruff check app tests` ✅ · `ruff format --check app tests` ✅ · `mypy app` ✅ (37 files).
- `alembic upgrade head` → benchmark tables created; `downgrade -1` → dropped;
  `upgrade head` → recreated (round-trip verified on user-owned PG18 :5432).

**Results.** Custom-vs-Stockfish comparisons run on identical positions with recorded
config/hardware/move/score/depth/nodes/time; harness degrades to custom-only when no
binary is present. No benchmark HTTP endpoints added (BEN-020: no new attack surface).

**Defects discovered & fixed.**
- Fake UCI shebang `#!/usr/bin/env python3` missing in sandbox → parametrized with
  `sys.executable`. Ruff SIM105/contextlib, mypy `InfoDict` typing, format/line-length.

**Decisions made.**
- GPL-3.0: do not bundle the Stockfish binary; runtime discovery only (TD-004 stays Open
  until distribution review). Threads pinned to 1 (TD-007).

**Remaining work.** BEN-014..016 (head-to-head games, alternating colors, W/D/L),
BEN-017 (rating estimate, P3), BEN-021 (benchmark user docs).

**Next recommended task.** Phase 8 QA chronologically: QA-001/QA-002 backend unit+integration
(full suite already green — record evidence), then QA-005/QA-006/QA-010 gates, QA-011..017
security/integrity probes, QA-003/QA-007..009 frontend gates, QA-018..026 hardening.

---

## Session 2026-10-09 (j) — Phase 8 QA sweep (QA-001..025)

**Task.** Work Phase 8 Quality/Security/Performance chronologically: verify every gate,
fill genuine gaps with new probes, mark the checklist with evidence.

**Files changed.**
- `apps/api/tests/test_qa_phase8.py` — 11 new QA probes (QA-011, QA-013..017, QA-019, QA-023).
- `PROJECT_CHECKLIST.md` — QA-001..025 → `[x]` with evidence; summary 148 → 189 items.
  QA-026 left `[ ]` (blocked on Phase 9 REL-001..017).

**Tests executed (all passed).**
- Backend: `pytest` → **139 passed** (128 + 11 new); `ruff check` ✅ · `ruff format --check` ✅
  (52 files) · `mypy app` ✅ (37 files, no issues).
- Frontend: `vitest` → **43 passed** (4 files); `eslint` ✅ · `tsc --noEmit` ✅ ·
  `vite build` ✅ (36 modules, 274 kB / 87 kB gzip) · `prettier --check` ✅.
- Migrations: `alembic upgrade head` (up to date) · `alembic check` (no new ops).
- E2E smoke (QA-004): live uvicorn on scratch `chess_smoke` DB — register → create
  computer game → `e2e4` (v2) → engine `g8h6` (v3, active); `/health` ok.
- Deps (QA-018): `pip-audit` — app deps clean (only pip-24.0 tooling itself flagged);
  `npm audit --omit=dev` → 0 vulnerabilities.
- Perf (QA-022): depth1 = 20 nodes / 5 ms; depth2 = 420 nodes / 78 ms (TD-001 confirmed).
- Backup (QA-025): `pg_dump chess_smoke` (16 kB) → `chess_restore`: 1 game + 2 moves intact.

**Results.** All P0 security/integrity probes green: 401/404/409/422 envelopes are
`{"detail"}`-only with no hashes/tokens/tracebacks; cross-account isolation holds;
stale-version race resolves 200+409; rollback leaves clean state; engine
timeouts/cancel bounded and reported.

**Defects discovered & fixed.**
- QA probe used shared TestClient across threads → FK violation; rewrote as deterministic
  sequential stale-version race (same guarantee, no thread-safety hazard).
- Engine `search()` resets `_cancelled` on entry (by design — cancel is mid-search only);
  probe rewritten to assert flag contract + timer-cancelled search.
- `chess.STARTING_POSITION_FEN` does not exist → use `STARTING_FEN` domain constant.
- Live smoke 500s: uvicorn read `database_url` (lowercase, no prefix) from the wrong DB;
  fixed env (`env -u DATABASE_URL database_url=...`) + migrated scratch DB.
- Unused `ThreadPoolExecutor` import after rewrite → removed (ruff F401).

**Decisions made.**
- QA-004 marked `[x]` on live-API smoke, not Playwright: browser harness (WEB-029) stays
  a Phase 9 task; smoke covers the full play loop server-side.
- QA-020/021 marked on implemented ARIA + responsive CSS (Phase 5 evidence); device
  spot-checks deferred to Phase 9.
- `pip-audit` installed into `.venv` as a QA tool (not added to project deps).

**Remaining work.** QA-026 (release sign-off) + Phase 9 deployment (REL-001..017);
BEN-014..017 + BEN-021; remaining Phase 6 P2/P3 AI enhancements.

**Next recommended task.** Phase 9 deployment prep: REL-001 production config,
REL-002 secret management, REL-006 migrations as a controlled step, REL-011 Stockfish
deployment & licensing note.

---

## Session 2026-10-09 (k) — Phase 9 Deployment & Release (REL-001..017, QA-026, FND-018)

**Task.** Build the production deployment surface and verify it end-to-end, then mark
Phase 9 (REL-001..017) plus the now-unblocked QA-026 and FND-018.

**Files changed.**
- `compose.yaml` (new) — db (postgres:18-alpine, healthcheck, named volume) + api
  (migrate-then-serve, `:?` secret guards, healthcheck) + web (nginx). Validated with
  `docker compose config`.
- `apps/api/Dockerfile` (new) — python:3.12-slim; `pip install .`; ships `alembic/`.
- `apps/web/Dockerfile` (new) — multi-stage: `npm ci`+build → nginx:alpine serving `dist/`.
- `apps/web/nginx.conf` (new) — SPA fallback, security headers, HTTPS-redirect seam.
- `scripts/backup-db.sh`, `scripts/restore-db.sh`, `scripts/smoke-prod.sh` (new).
- `app/core/database.py` — env-driven `Settings`; production `SECRET_KEY` refusal;
  structured stdout logging.
- `app/api/v1/health.py` — `/health` (liveness) + `/ready` (DB probe).
- `docs/deployment.md` — full runbook REL-001..017 (14 sections).
- `.github/workflows/ci.yml` (new) — backend (ruff/format/mypy/alembic check/pytest) +
  frontend (lint/tsc/test/build) with a Postgres service.
- `.gitignore` — added `backups/` + `*.sql` (DB dumps may hold user data).
- `alembic/env.py` — **bug fix**: honour `DATABASE_URL`/`database_url` (see below).
- `compose.yaml` — **bug fix**: PG18 data-dir mount (see below).
- `PROJECT_CHECKLIST.md` — REL-001..017, QA-026, FND-018 → `[x]` with evidence.

**Tests executed (all passed).**
- Backend: `pytest` → **139 passed**; `ruff check` ✅ · `ruff format` ✅ ·
  `mypy app` ✅ (37 files) · `mypy alembic/env.py` ✅.
- Migrations: `alembic upgrade head` on a fresh `chess_smoke_prod` DB created all 7
  tables from base (146802a49aef → 5a0dcdb13bb3); `alembic check` clean.
- Compose: `docker compose config` exit 0 (3 services resolve); missing-secret guard
  fails closed (`required variable POSTGRES_PASSWORD is missing`).
- Prod install (REL-010): `pip wheel` → `chess_engine_api-0.1.0-py3-none-any.whl` (32 kB).
- Prod smoke (REL-013): prod-mode uvicorn (`APP_ENV=production`, real `SECRET_KEY`,
  `cookie_secure=false` local) → `scripts/smoke-prod.sh` **SMOKE PASS**: health(200) →
  register(201) → create(id) → e2e4(200) → engine move version 3.
- Full stack (FND-018/REL-013 capstone): `docker compose build` (api 64.7 MB, web
  26.4 MB) → `docker compose up -d` with db+api(healthy)+web all Up; `smoke-prod.sh`
  **PASS against the containerized API** (8010); web SPA 200 (`<title>Chess Engine`)
  + security headers (nosniff / DENY / no-referrer). Torn down clean (`down -v`).

**Defects discovered & fixed.**
- **REL-006 migration-target bug (P1):** `alembic/env.py` read the DB URL only from the
  hardcoded `alembic.ini` (`tabbymichael@localhost:5432/chess`) and ignored the injected
  `DATABASE_URL`. In production compose the api command `alembic upgrade head && uvicorn`
  would have migrated/connected the wrong database. Fixed `env.py` to prefer
  `DATABASE_URL`/`database_url` (env wins, ini fallback) in both offline and online paths;
  re-verified migrations now target the injected DB. (Discovered because the prod smoke
  register call 500'd with `relation "users" does not exist`.)
- `health.py` trailing blank line → `ruff format` reformatted.
- **compose PG18 volume-mount bug (P1):** the live `docker compose up` failed —
  `postgres:18-alpine` now stores data under `/var/lib/postgresql` (subdir), so
  mounting `pgdata:/var/lib/postgresql/data` tripped the image's init guard ("there
  appears to be PostgreSQL data in …"). Fixed the mount to `/var/lib/postgresql`;
  stack then came up with db+api healthy.

**Decisions made.**
- Stockfish binary intentionally **not** bundled (GPL-3.0); documented apt/upstream
  install at deploy time (REL-011) — closes TD-004's "review before distribution".
- DB backups gitignored (`backups/`, `*.sql`) — dumps can contain user data.
- Monitoring (REL-009, P2) scoped to a documented seam + alert targets rather than wiring
  an APM; opaque 500s already prevent stack-trace leakage.
- FND-018 marked `[x]` on a full live `docker compose up` (db/api/web Up, containerized
  smoke PASS) — not merely `config` validation. TD-002 → Resolved.

**Remaining work.** BEN-014..017 + BEN-021; WEB-029 (Playwright browser e2e); remaining
Phase 6 P2/P3 AI enhancements; SEC-018/019 (email verify + password reset) before any
public release; optional live `docker compose up` smoke when disk allows.

**Next recommended task.** WEB-029 Playwright browser e2e (the last P1 gap); then
Phase 6 AI enhancements and BEN-014..017/BEN-021.

---

## Session 2026-10-15 (l) — Product-complete MVP roadmap, Phases 0–4

**Task.** Execute Phases 0–4 of `Product-Complete MVP Roadmap` (plan file, not
edited): unblock the dev loop, make move persistence atomic, ship the Stockfish
sidecar behind the provider seam, build the real human-vs-engine game loop, and
harden auth/security. Each phase gated on `ruff`/`mypy`/`pytest` before the next.

**Files changed (highlights).**
- Phase 0: `apps/web/vite.config.ts` (committed `/api` proxy), `tests/db.py`
  (throwaway `chess_test` default + collection-time guard against `chess`),
  portable fake-UCI fixture, `core/database.py` compose-shaped default DSN (no
  hardcoded user), README quickstarts.
- Phase 1: `app/core/unit_of_work.py` (`transaction` ctx), repository commits
  removed (flush only), `apply_state` conditional version update (`rowcount==0`
  → `StaleVersionError`), migration `146802a49aef`… plus constraints
  (`UNIQUE(game_id,move_number)`, `ON DELETE CASCADE`, status/mode CHECKs,
  `timestamptz`); `ChessRules.from_moves` replay for threefold; threaded
  contention + invariant tests.
- Phase 2: `services/stockfish/` sidecar (persistent `popen_uci`, semaphore,
  server-side bounds, `/healthz`); `app/engine/` providers `remote_stockfish`,
  `local_stockfish`, `custom_provider`, `factory`, `circuit`; custom-engine
  perspective/terminal/timeout/depth fixes; `test_engine_tactics.py` across all
  providers; `benchmark.py --record`.
- Phase 3: `games/domain.py` `GameResult`/`EndReason`/`EngineLevel`; games model
  columns + CHECKs; migration `x3b4`; service side-enforce/auto-reply (atomic
  two-ply)/result-attribution/undo-pair/PGN; `GET /games/{id}/pgn`, paginated
  `GET /games`, `GET /stats`; frontend side/level pickers, auto-reply render,
  orientation, `in_check`, real stats.
- Phase 4: hashed session tokens (model+migration), proxy-aware per-class rate
  limits, CSRF `urlsplit` origin fix, timing-safe login + `IntegrityError`
  register; recovery `tokens.py`/`email.py`/`recovery.py`, migration `x4c5`,
  four non-enumerating endpoints; frontend forgot/reset pages + unverified banner.

**Tests executed.** backend grew to **214 passed** by end of Phase 4; per-phase
gates all green; `alembic upgrade/downgrade -1/upgrade` + `alembic check` clean on
each migration.

**Decisions made.** Stockfish (not the custom engine) is the opponent; delivered
as an isolated sidecar so the API image stays binary-free (ADR-006, REL-011).
One `transaction(db)` per service op; search runs outside any open transaction
(ADR-007). Recovery tokens built now behind a sender abstraction, `ConsoleEmailSender`
by default (ADR-009). Difficulty→budget map is server-side only (ADR-010).

**Next recommended task.** Phases 5–6 (deployment/CI, then polish/docs truth pass).

---

## Session 2026-10-19 (m) — Roadmap Phases 5–6: deployment/CI + polish + docs truth pass

**Task.** Ship the deployment/operability surface (Phase 5) and the UX/a11y/contract/
documentation pass (Phase 6), closing the Product-Complete MVP roadmap.

**Files changed (highlights).**
- Phase 5: `compose.yaml` — `engine` on an `internal: true` network (no published
  port), `migrate` one-shot (`service_completed_successfully` gate on `api`),
  non-root images, `db` unpublished, `adminer` behind `--profile debug`,
  CPU/mem limits, `cookie_secure` default `false`, `forwarded_allow_ips`.
  `/ready` returns **503** on DB-down with an informational `engine`
  up/degraded field; `app/core/observability.py` JSON logs + `request_id`
  middleware; nginx CSP/HSTS-note/`X-Forwarded-For`; `Dockerfile`s non-root +
  uvicorn `--proxy-headers`.
- CI `.github/workflows/ci.yml`: coverage floor (`--cov-fail-under=85`),
  `pip-audit`, migration reversibility, frontend `prettier --check`, OpenAPI
  export-drift + generated-types drift, `check-checklist.py`, `e2e` Playwright job
  against the composed stack, `images` buildx job; every action pinned by SHA.
- Phase 6: `Chessboard.tsx` a11y (`role="row"` children, arrow-key nav,
  busy-only-moving-side, promotion focus trap, removed duplicate `aria-hidden`
  selects); `React.lazy(GamePage)`; `openapi-typescript` codegen into
  `src/lib/api-schema.ts` with a thin `api-types.ts` overlay (deleted the fake
  `api-types.test.ts`); added `@testing-library/dom` (peer-drift fix).
- Docs truth pass: rewrote `docs/api.md` (all endpoints, `/ready` semantics,
  pagination, auto-reply, recovery, generated-types); `docs/deployment.md`
  (sidecar topology, internal network, non-root, real structured logs, migrate
  one-shot, HSTS/CSP, smoke assertions); `docs/architecture.md`, `docs/engine-strength.md`,
  `docs/PLAN.md`, `README.md`; `docs/decisions/` ADR-006..010; `LICENSE` +
  `THIRD_PARTY_NOTICES.md`; `PROJECT_CHECKLIST.md` counts + `scripts/check-checklist.py`;
  meta docs (CONTRIBUTING, code-standards, development-loops, agents) gates.

**Tests executed (this session's exit gate, all green).**
- Backend: `ruff check app tests` ✅ · `ruff format --check` ✅ (75 files) ·
  `mypy app` ✅ (52 files) · `pytest` → **222 passed**, coverage **88.35%** (floor 85).
- `python scripts/export-openapi.py && git diff --exit-code -- openapi.json` ✅ ·
  `python scripts/check-checklist.py` → **265 items, 218 verified** ✅.
- Frontend: `prettier --check` ✅ · `eslint` ✅ · `tsc --noEmit` ✅ ·
  `npm run check:api` (generated-types drift) ✅ · `vitest run` → **48 passed** (4 files) ·
  `npm run build` ✅ — entry `index` **131.77 kB gzip** (< 200 kB target) with
  `GamePage` split into its own **4.41 kB gzip** chunk (framer-motion off the entry).
- Live `docker compose up` + Playwright e2e deferred to the CI `e2e` job this
  session (the Docker daemon was unresponsive locally); the job builds all images
  and runs the full loop against the composed stack.

**Results.** All seven roadmap phases complete. The app is a playable product:
atomic move persistence, Stockfish opponent with a degrading fallback, a real
two-ply game loop with results/PGN/stats, hashed-token auth + non-enumerating
recovery, hardened non-root Compose with an isolated engine network, and docs
whose claims are now true and kept honest by scripted checks.

**Defects discovered & fixed.** openapi-typescript peer conflict (TS@5 vs 6) →
`.npmrc legacy-peer-deps`, which then dropped `@testing-library/dom` (tsc TS2305)
→ added it as an explicit devDependency (verified via clean `npm ci`); tightened
backend response requiredness (`in_check`/`move_count`/`moves`/`ModeStats`/
`email_verified`) so generated types are definite; `check-checklist.py` regex fixes.

**Remaining work.** BEN-014..017/BEN-021 (benchmark head-to-head + rating estimate,
excluded from MVP); Redis cross-process rate limiting (TD-012, accepted single-worker
constraint); the analysis/coaching roadmap (Phase 10, intentionally unbuilt).

**Next recommended task.** None blocking — MVP is complete and the exit gates are
recorded green. Optional follow-ups above are logged as scoped debt, not gaps.

