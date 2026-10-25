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

## Session 2026-10-23 (l) — Online human-vs-human play (online-play-plan Phases 1–4)

**Scope.** The biggest missed product feature: two accounts queue, get paired,
and play each other with the same server-authoritative core. Implemented
Step 0 (shared move kernel), Phase 1 (migration + online service), Phase 2
(lobby + REST), Phase 3 (WebSocket), Phase 4 (frontend lobby & live board).

**What was built.**
- Step 0 refactor (no behavior change): `apply_and_store_move` kernel + public
  `require_version/require_active/require_not_online` + per-user
  `award_points(db, user_id, …)` in `app/games/service.py`; terminal awards
  unified in `sync_status` (computer + online seats); `get_by_participant`
  (OR-of-seats) in `game_repository`; registry-driven test wipe + ephemeral
  state reset fixtures in `conftest.py`.
- Migration `a1c7e4f9b2d6`: `games.white_user_id` / `games.black_user_id`
  (nullable, indexed, FKs) + `GameMode.ONLINE`. `user_id` mirrors White on
  online games so every legacy owner-scoped query keeps working (plan §12).
- `app/games/online_service.py`: turn-checked moves, resign (loss/win seats),
  position-based draw claims (both seats +5), participant-scoped get/list.
  `POST /games` now refuses `mode=online` (422) — only the lobby creates them.
- `app/games/lobby.py` (in-process queue, duplicate guard, random colors) +
  `/online/queue` POST/DELETE/GET, `/online/games*` REST routes with per-user
  move rate limiting (`MOVE_RATE_LIMIT_PER_MINUTE`, 429) and same-origin guards.
- `app/games/hub.py` + `GET /online/ws`: cookie-auth handshake with close codes
  4400/4401/4403, 4 KB frame cap, 10 msg/s, session-per-message, `game_state`
  broadcasts to both seats; REST stays the authority (plan §6.2).
- Frontend: `QueueResponse`/seat types, online api-client methods, `Delete`
  support, `lib/online-ws.ts` (backoff reconnect + heartbeat), `/lobby` and
  `/online/:id` pages (turn-gated board, REST polling fallback, resign/draw),
  Dashboard “Online match” mode routes to the lobby.

**Tests.** Backend: +27 (11 service, 10 REST/lobby incl. create-mode guard,
6 WebSocket handshake/broadcast/disconnect); full suite 161 → 188 green.
OpenAPI contract test now requires the six /online paths. Frontend: +11
vitest (lobby 4, online board 7 with faked socket); suite 70 → 81 green.

**Gates.** ruff check/format, mypy (47 files), `alembic upgrade head` +
`alembic check`, full pytest; eslint, `tsc --noEmit`, vitest, `vite build`
— all pass locally (CI runs the same commands).

**Decisions / known limits.**
- D6 (architecture): lobby, socket hub, rate buckets are single-process
  state islands; restarts drop matchmaking but never games. Multi-replica
  needs Redis/pubsub — recorded as accepted debt.
- WS `opponent_left` is advisory: a player leaving mid-game does not forfeit
  (no clocks in v1; plan leaves timeouts to a later phase).

**Next recommended task.** Online Phase 5 (restart-drain messaging, replay
protection via game move caps) + WEB-029 Playwright e2e covering the lobby
flow; then Track B (Game Analysis, Phase 9).

---

## Session 2026-10-23 (m) — Play feel, real opponent, game review, achievements

**Scope.** Four product gaps in one batch, sequenced so each landed green before
the next started: (P1) sound + haptic feedback with a promotion-picker bug fix,
(P2) Stockfish as the actual computer opponent, (P3) post-game engine review that
grades and explains every move, (P4) a 200+ achievement catalog with
celebrations. Tracked as Phase 10 (FEEL/PLAY/REVIEW/ACH) in `PROJECT_CHECKLIST.md`.

**What was built.**
- **P1 — play feel.** `lib/sound.ts` (synthesized WebAudio presets per event,
  intensity-scaled gain, inert without WebAudio), `lib/haptics.ts` (Vibration
  patterns, prefers-reduced-motion aware), `lib/settings.ts` (localStorage prefs
  + subscribe), `lib/game-events.ts` (`classifyMove` + `emitMoveSequence`, which
  walks plies FEN-forward so your own move, the engine reply and an online
  broadcast are classified against the position they were made from),
  `lib/useGameFeedback.ts`, `SoundToggle`, wired into `GamePage` +
  `OnlineGamePage`. A rejected move now plays the error sound **without** a
  banner. Promotion fix: `isLegalPromotion` (chess.js) gates the picker, so a
  pawn tapping the last rank outside promotion territory no longer opens it.
- **P2 — opponent.** `app/engine/opponent.py` answers computer games through the
  existing `EngineProvider` seam with bounded Stockfish (`DIFFICULTY_*` depth
  mapping keeps the difficulty UI meaningful); failures surface as `503`
  `EngineUnavailableError` rather than silently reverting to the old minimax.
  `tests/conftest.py` grew a `fake_binary` fixture (PATH-resolved UCI script
  emitting multiplexed `info … multipv N` lines) so the whole suite stays
  hermetic without a real engine installed.
- **P3 — game review.** `app/engine/classifier.py` (seven grades from centipawn
  loss against a MultiPV=3 window, mate-distance blending, forced-move and
  sacrifice context, published thresholds), `app/reviews/explainer.py` (rule
  templates that cite stored facts: capture victim, missed alternative, praise
  for the engine's own move), `app/reviews/service.py` (bounded analysis pass,
  per-(game, player) storage, `force` updates in place), model + migration
  `c5e9a3d7f410`, `POST/GET /games/{id}/review` (404/409/422 semantics) and the
  frontend `/games/:id/review` page: SVG eval graph (`EvalGraph.tsx`),
  click-a-ply board replay via stored `pre_fen`, report card, improvement list
  filtered to the colour you played, re-analyse button.
- **P4 — achievements.** `app/achievements/catalog.py` (32 ladders over one
  metric each = **316** entries, bronze→legendary, import-time asserts on key
  uniqueness and the 200+ requirement), `stats.py` (SQL `FILTER` aggregates over
  stored moves by SAN pattern, point-ledger results, review payload grades,
  active-day streaks), `service.py` (idempotent `flush`, gallery, pending,
  `mark_seen`), model + migration `d7f3b0c9e512`, `GET /me/achievements`,
  `GET /me/achievements/new`, `POST /me/achievements/seen`. Unlocks **ride** the
  response that earned them (`GameResponse.unlocked_achievements`, review
  responses) and the private WS `achievement` event is sent to one seat only.
  Frontend: `AchievementContext` queue (de-dupes ride vs lazy catch-up),
  confetti toast with rarity ring + auto-dismiss + acknowledgement,
  `/achievements` gallery (grouped, filterable, progress bars), dashboard strip
  of real recent unlocks replacing the four hardcoded mock badges.

**Defects discovered & fixed during the work.**
- `Move.uci` is a **method** in python-chess, not a property (mypy caught it);
  `chess.square_relative` does not exist — the en-passant victim is
  `to_square ^ 0x10` when the move is en passant.
- `force: true` review generation would have inserted a second row per
  (game, player) and violated `uq_game_review_per_user`; `generate_or_get` now
  reuses and updates the stored row.
- Reviews read through `GameRepository.get_moves`, which filters on the owner
  column (mirroring the White seat) — an online **Black** reviewer got an empty
  move list. Replaced with an explicit unfiltered select for the review path.
- eslint `react` rule rejected a synchronous `setState` inside the review page's
  load effect; restructured into a promise chain that only setStates in callbacks.
- `OnlineGamePage` used the strict `useAchievements()` hook, which throws when a
  page renders without the provider (it broke the existing online tests); added a
  tolerant `useAchievementsOptional()` so feedback stays layered on the board.
- The private-socket celebration test asserted the toast with the default 1 s
  `findByText` window while the backend suite was competing for CPU on the same
  runner, and timed out. The assertion waits on two independent chains (auth
  restore gates the queue, then the socket event), so it now allows 3 s instead
  of relying on an idle machine.

**Tests.** Backend 188 → **245** pytest (`test_opponent` 4, `test_reviews` 17,
`test_achievements` 31 incl. catalog-vs-stats metric coverage, ride delivery and
"never the opponent"); OpenAPI contract test now requires the review and the
three achievement paths. Frontend 81 → **143** vitest across 15 files (+35
achievement tests: helper maths, gallery, toast timers, provider de-duplication,
private socket event, provider-less page).

**Gates.** ruff check + format (82 files), mypy (59 files), `alembic upgrade
head` from an empty database + `alembic check` (no drift), full pytest; eslint,
`tsc --noEmit`, vitest, `vite build` (383.67 kB JS / 119.60 kB gzip, 30.39 kB
CSS) and `prettier --check .` — all pass locally (CI runs the same commands).

**Decisions / known limits.**
- D7/D8/D9 recorded in `docs/architecture.md`: Stockfish opponent with no silent
  weaker fallback; achievement catalog in code with only unlock rows in the DB;
  review computed synchronously once per (game, player) and served from storage.
- Heavy achievement aggregation runs on terminal game transitions and on demand
  (`GET /me/achievements/new`), not on every ply.
- `wins/draws/losses/active_days/best_streak_days` derive from the point ledger,
  which local hot-seat games never write — a local-only player sees 0 for those
  metrics (their mode-specific ladders still count games). Registered as debt.
- Not yet built from the Phase 9 design: worker pool, win-probability model, eval
  cache, async analysis jobs, tactics detection, ELO-aware thresholds, PGN import,
  retry-the-move (kept `[ ]` in the checklist with what partially exists noted).


## Session 2026-10-23 (n) — "Stockfish binary not found" in the running stack

**Report.** The live compose stack answered computer moves with
`Stockfish binary not found. Install the 'stockfish' package or set STOCKFISH_PATH.`,
and the player pointed at `STOCKFISH_API_KEY` in `.env` expecting it to be the engine.

**Root cause.** The production image *does* install Stockfish (`apt-get install
stockfish`, added with PLAY-001), but Debian ships it to `/usr/games/stockfish`
and slim images keep `/usr/games` off `PATH`. `compose.yaml` passes
`stockfish_path: ${STOCKFISH_PATH:-}` and `.env` leaves it empty, so
`resolve_binary()` had only a `PATH` lookup to work with and concluded there was
no engine in an image that contains one. The dev image had been saved all along
only because `compose.dev.yaml` hardcodes `/usr/games/stockfish`.

**The API key is dead config.** `settings.stockfish_api_key` is loaded and read
by nothing — there is no hosted provider implementation. `.env` / `.env.example`
now say so explicitly instead of advertising "cloud engine, no binary needed".

**Fixes.**
- `resolve_binary()` probes a constant list of distro package locations after
  `PATH` (`/usr/games`, `/usr/bin`, `/usr/local/bin`, `/opt/homebrew/bin`), with
  an explicit `STOCKFISH_PATH` still winning. Never client input (BEN-020).
- Engine startup is now tolerant and bounded: `_start_engine()` asks python-chess
  for a 20 s handshake (default 10 s) and retries once. Live verification hit an
  intermittent `503 Could not start Stockfish ...` with an *empty* reason — a bare
  `TimeoutError` from a stalled UCI handshake under CPU contention, i.e. an
  engine that was present and fine being reported as unavailable.
- **Accuracy was inverted.** `_accuracy()` shipped as
  `103 * (1 - e^(-acl/150))`, which grows with centipawn loss: a game in which
  every ply was the engine's own top choice reported **0%**. It is now
  `100 * e^(-acl/250)` (100 flawless, ~96 at acl 10, ~67 at acl 100, ~37 at the
  scale point), documented as an approximation rather than a calibrated model.
  The old test only asserted `0 <= accuracy <= 100`, which the wrong formula
  satisfied — the new tests pin the anchors and the direction.
- `docs/deployment.md` §10 rewritten: the binary is not vendored but *is*
  installed into both images, publishing such an image is redistribution under
  GPL-3.0, discovery order, and that a missing binary now means a clean 503 with
  **no** fallback to the custom engine (D7) — the previous text claimed the
  custom engine kept running.

**Verified against the real binary in the container** (`docker compose build api
&& up -d`): `resolve_binary()` → `/usr/games/stockfish`; 10/10 consecutive engine
moves succeeded (0.37–1.62 s each, previously one 503 in ten); a finished 20-ply
game reviewed in 24.6 s with sensible accuracy (`w: 20, b: 72`) and cached on the
follow-up `GET`; 11 achievements rode one resign response.

**New defects found by that verification, recorded not papered over.**
- TD-013 now carries the measured cost: ~1.2 s per ply, one spawned process per
  ply, synchronous — a long game is a multi-minute request.
- TD-017: moves outside the engine's MultiPV=3 window are charged the
  `_OFF_TABLE_CP = -800` placeholder, so six of twenty plies were labelled
  "blunder — gives up 8.0 pawns" for moves that were simply not the engine's
  first choice. The grades are systematically too harsh off-window; fixing it
  needs the off-window position evaluated for real (ANL-003/ANL-005 first).

**Tests & gates.** Backend 245 → **254** pytest (+5 engine resolution/startup,
+4 accuracy), full suite green; `ruff check`, `ruff format --check` (82 files),
`mypy app` (59 files) clean; image rebuilt and health-checked. No frontend change
in this session (143 vitest still valid).


## Session 2026-10-24 (o) — TD-017 off-window grading, ANL-003 warm engine, hosted Stockfish fallback

**Report (again).** The player still saw
`Stockfish binary not found. Install the 'stockfish' package or set STOCKFISH_PATH.`
in the browser and pointed at `STOCKFISH_API_KEY` in the repo-root `.env`,
expecting the hosted key to be the engine. Two independent problems.

**Root causes.**
1. The literal was a *stale persisted review row* (status `failed`) from before
   session (n) shipped the distro-path probe. The rebuilt container already
   resolves `/usr/games/stockfish`; the banner clears only when a fresh review
   overwrites the row.
2. The hosted key genuinely did nothing: `Settings` uses
   `env_file=".env"` **relative to the process cwd**, so a host `uvicorn` loads
   `apps/api/.env` (no key), while the repo-root `.env` is only read by
   `docker compose` for interpolation. And there was no hosted provider at all
   — the key was dead config (as session (n) recorded).

**Shipped this session.**
- **TD-017 (Resolved).** Off-window moves are graded from their own post-ply
  evaluation (`_position_value`/`_line_score`, terminal-aware `_terminal_value`)
  instead of the `-800` placeholder. On the same 20-ply smoke game the false
  "blunder" count dropped 6 → 1, and the one left is a real ~420 cp loss.
- **ANL-003 (done).** `StockfishProvider` is now a context manager: inside
  `with`, one warm process serves the whole review batch; a failed analysis
  drops the process rather than reusing a dead one. Measured 20-ply review
  **~12 s** warm-batch vs **~24.6 s** one-process-per-ply (TD-013 repaid in part
  — ANL-008 job queue still open for long games).
- **Hosted provider (`app/engine/cloud_stockfish.py`).** A real
  `CloudStockfishProvider` behind the same `EngineProvider` seam, for
  stockfishapi.com `POST /eval`. Bounded depth (free plan ≤14), one bounded
  retry, RFC-9457 problem summary that never echoes the key or raw body, and a
  **runtime calibration probe** for the undocumented score POV (Black-to-move,
  queen-up FEN; defaults to mover-POV if the probe fails, cached process-wide).
- **Provider factory (`app/engine/factory.py`).** One local-first / hosted-
  fallback decision shared by play (`opponent.py`) and review (`reviews/service.py`):
  resolve a binary, else use the key, else raise one error naming both fixes.
  Review records the answering engine (`review.provider = provider.name`).
- **`BatchedEngineProvider`** protocol added to `provider.py` so the review's
  `with` usage is typed for both providers.
- **Env wiring.** `compose.yaml` and `compose.dev.yaml` forward
  `STOCKFISH_API_KEY` / `STOCKFISH_API_BASE_URL` into the api container (dev
  override now repeats the full env map because compose replaces, not merges).
  `apps/api/.env` mirrors the key so host `uvicorn` reads it too; the stale
  "NOT WIRED UP" comments in `.env`/`.env.example` are corrected.
- **`requirements.lock`.** Added the runtime deps that were declared but
  untracked: `requests`, `urllib3`, `google-auth`, `pyasn1`, `pyasn1_modules`.

**Live verification.** Against the running container: register → computer game →
10 engine moves (avg 0.5–0.8 s, slowest 2.3 s) → resign → 20-ply review
`status=completed provider=stockfish` in ~12 s, grade distribution sensible (no
false-blunder pile-up). The hosted route was exercised with a fake-hidden binary:
the factory returns `CloudStockfishProvider`; a live probe returned the account's
documented `402 Payment method required`, surfaced cleanly as a `503` — the key
works as wiring, but this account is not yet enabled for paid usage, which is
why the local binary stays the primary path.

**Tests & gates.** Backend **254 → 291** pytest (+30+ cloud-provider/factory,
+off-window grading, +warm-engine lifecycle); `ruff check`, `ruff format --check`,
`mypy app` clean; frontend 143 vitest unchanged (no web code change beyond the
review `provider` field already surfaced). Conftest disarms both local and hosted
Stockfish so no test ever touches a real engine or the network.


## Session 2026-10-24 (p) — Review tour: opening names, win expectancy, calm voice

**Request.** "When analysis is done the board goes back to the start of the game
and I am able to move through it with front and back icons, as you explain the
moves — which opening is that, probabilities of winning with that opening. Retain
everything we have in the analysis page. Also implement a voice when explaining
the moves: calm, authoritative and free."

**Three questions asked before designing** (each answer changed the architecture):
odds source → **engine expectancy only**, not third-party result statistics;
trigger → **speak on each step**, no auto-play tour; board → **step through the
recorded plies only**, so it stays read-only and no new move path appears here.

**Facts verified first, because they chose the design.**
- `chess.opening` **does not exist** in the installed python-chess 1.11.2 (its RECORD
  ships engine/gaviota/pgn/polyglot/svg/syzygy/variant only). Offline names must be
  vendored, not imported.
- `lichess-org/chess-openings` is **CC0 / public domain** — `a.tsv`..`e.tsv`,
  columns `eco name pgn`, no NAGs/comments in the sampled rows. It keys each line's
  **final** position (TD-018), which is why the carry-forward rule exists.
- The Lichess opening explorer hosts were **unreachable from this machine** (DNS
  failure, `code=000`), so live "win rate with this opening" data would have been
  unverifiable locally and a CI coin-flip. Expectancy computed from the eval the
  review already stores needs no network at all.
- `chess.Board.epd()` ignores move counters and the en-passant field, which makes it
  a stable theory-position key (Ruy Lopez verified: `… b KQkq -`).
- The Dockerfile runs `pip install .` and `[tool.setuptools.packages.find]`
  includes only `app*`, so a `.json`/`.tsv` asset would have worked in the editable
  venv and silently vanished in the image. The book therefore ships as a
  **generated Python module holding one TSV string**.

**Shipped this session — backend.**
- **Offline book (`app/openings/`).** `scripts/gen_opening_book.py` fetches the five
  TSVs, normalises (move numbers, game results, `!?` annotations dropped; `0-0-0`/
  `0-0` → `O-O-O`/`O-O`), replays each line through `chess.Board.push_san()` and
  writes `book_data.py` — **3,865 positions**, 424 KB, deterministic (identical md5
  across reruns, 0 lines skipped). It aborts loudly on a network failure and on a
  suspiciously short result, because the generated file is what ships. `book.py` is
  pure lookup: `@functools.cache` over the string, duplicate EPDs keep the most
  specific name (most `:` segments), `opening_after(pre_fen, uci)` never raises.
- **Win expectancy (`app/engine/win_probability.py`, ANL-004).** Logistic on the Elo
  equivalent of the eval — `ELO_PER_CENTIPOWN = 2.0` (one pawn ≈ 200 Elo ⇒ 76%) —
  computed on the magnitude then mirrored, so `win_pct(-cp) == 100 - win_pct(cp)`
  exactly; clamped 1..99; a mate distance decides instead (99/1 within five moves,
  95/5 beyond). Pure function: `app/engine/` stays HTTP- and DB-free.
- **Read-time annotation (`app/reviews/annotate.py`).** Adds `opening_eco`,
  `opening_name`, `in_book`, `win_pct` per ply, flipping the mover-POV eval to White's
  perspective, and carries the deepest match forward so a game that leaves theory
  still names the opening that got there. Returns copies — the stored payload is
  never mutated. Wired in `to_review_response` only, so the cached `GET` and the
  fresh `POST` share one path. Four optional fields on `ReviewMoveResponse`, so
  **no Alembic revision and no forced re-analysis**: reviews written before this
  session light up on the next read.

**Shipped this session — frontend.**
- **The tour.** `ReviewPage.tsx` lands on ply 1 (one `initialPly` helper replacing
  both "jump to last ply" sites; ply 1's `pre_fen` *is* the start position, so no
  synthetic ply 0 was needed and the graph and move list keep working). First/Prev/
  Next/Last strip with a `Move n of N` counter, disabled at both bounds, plus one
  `window` `keydown` listener (`ArrowLeft`/`ArrowRight`/`Home`/`End`, skipped when a
  modifier is held or the target is a field/button, removed on unmount). The board
  stays `disabled` — navigation only ever moves the cursor.
- **Opening and odds card.** ECO · name, an `In book` / `Out of book` badge, the
  hero-side expectancy bar (`winPctFor` flips White's number for a Black player),
  and this game's family average (`openingAverage` over plies sharing the text
  before the first `:`). Every existing card — board line, eval graph, report card,
  where-to-improve, move list — is untouched.
- **Voice (free, offline, OS-supplied).** `lib/voice.ts`: feature-detected
  `speechSynthesis`, rate/pitch 0.92 for a calm read, `cancel()` before every
  `speak()` so fast stepping replaces instead of stacking, sentence-aware chunking
  at ≤180 chars (Chrome drops an utterance around 15 s; a naive punctuation split
  would tear "1.5 pawns"), voice chosen from an ordered hint list then en-GB then
  any `en-*` then the platform default. `lib/narration.ts` puts the payload into
  English: `Nf3` → "knight to f3", `exd5` → "the e-pawn takes d5", `O-O` → "castles
  kingside", `Qxh7#` → "queen takes h7, checkmate", `12 cp` → "12 points", dashes →
  commas; no opening name means the clause is dropped, not read as "unknown".
  `VoiceToggle.tsx` on a new `voice` preference (default on), hidden entirely where
  no speech engine exists; a `useEffect` speaks each step but a ref keeps the
  automatic first render silent, because browsers drop gesture-less speech.
- **Two deliberate deviations from the approved plan**, both because the plan's
  approach was measurably worse: Chrome's `voiceschanged` listener is replaced by
  per-call voice resolution (the listener can only ever arrive one step late, and
  every step re-asks anyway); `narratePly(move)` speaks from **the mover's** side
  rather than taking a `heroColor`, because naming the player is what makes a
  spoken board position unambiguous.

**Defects found and fixed while verifying.**
- An ad-hoc verification probe read the generated TSV with the *source* column order
  (`eco name pgn`) instead of the *generated* one (`epd eco name`), so a correct book
  looked like a missing entry. The book was right and the probe was wrong — recorded
  here because the same confusion would waste the next reader's time.

**Live verification.** Against the rebuilt image, with **no bind mounts** (so the
test is of packaging, not of the host tree): `book_size()` → 3865 inside the
container, proving the module ships under `pip install .` (D10). `GET
/api/v1/games/34/review` on a **stored** row whose payload provably lacked the new
keys (`best_uci…uci`, 12 fields) returned `200` with all four derived fields and no
engine pass: `B00 → C20 → C40 → C44 → C60 Ruy Lopez → C70 Morphy Defense`, with
`in_book: false` from `4.Ba4` onward while still naming the Ruy Lopez. Coverage on
the two stored reviews: 16/16 and 46/46 plies named and given odds (TD-018).

**Tests & gates.** Backend **291 → 344** pytest: `test_openings.py` and
`test_win_probability.py` = 45 collected (names asserted against the generated file,
not from memory; a row-count floor so a truncated generation cannot pass silently;
monotonic/mirror/mate-clamp properties) and 8 new `TestReviewAnnotation` cases in
`test_reviews.py` (fields filled, carry-forward after the book ends, payload dicts
not mutated, an old payload still serialising). Frontend **143 → 207** vitest:
`voice.test.ts` 16, `narration.test.ts` 28, `review.test.ts` 18, and
`ReviewPage.test.tsx` 8 → 19 with all eight originals passing **unchanged** — that
is the "retain everything" check. Gates in CI order: `ruff check` + `ruff format
--check` (93 files), `mypy app` (66 files), `alembic current` unchanged at
`d7f3b0c9e512` + `alembic check` → "No new upgrade operations detected" (no
migration was added), eslint, `tsc --noEmit`, vitest, `vite build` (391.56 kB JS /
122.23 kB gzip, 31.49 kB CSS), plus `prettier --check src`.

**Decisions & tracking.** Architecture **D10** (offline CC0 book shipped as a
generated module, resolved at read time) and **D11** (engine expectancy, never a
population result rate); `openings` added to the module table with its own "must
NOT" column. `PROJECT_CHECKLIST.md`: **ANL-004 ticked**, **COA-004** and **CLS-001**
re-scoped to what actually exists, new **REVIEW-007/008/009** ticked. `docs/api.md`
gains the "derived on read, not stored" section (formula, provenance, POV rule).

**Remaining / next task.** COA-004 still owes the deviation-from-theory and
plan-per-opening halves (the book names positions only); CLS-001 still owes
grading on win%-drop now that the model exists (TD-016); TD-018 covers the
final-position indexing. The voice layer is only provable as a guarded no-op under
jsdom — vitest asserts the calls and the chunking, never the sound, so the calm
read itself needs a human ear in a real browser. Next: that browser pass on
`/games/:id/review` (narration quality, voice selection, the strip on a touch
device), or COA-004's deviation detection — compare the played ply against the
book's alternatives at that EPD — as the following slice.

## Session 2026-10-24 (q) — Learn: themed drills, your own missed moves, animated review loader

**Request.** Add a `/learn` section — themed skill cards, an interactive drill
board, puzzles taken from the player's own analysed games, per-skill progress with
an easy→hard ramp, points and achievement ladders — and make the review loader a
live board that replays the game **backwards** while Stockfish thinks, instead of a
bare text card. Closes **REV-005**, advances **TAC-001/002**, opens the **LEARN-**
stage.

**Facts verified first, because they chose the design.**
- python-chess can prove a *single-move* drill sound by pattern (FEN valid, solution
  legal, theme goal met through the forced line, `mate_in_one_exists` before/after a
  back-rank escape) **without any search** — which is exactly why drills are
  hand-authored and machine-re-proved (`verify.py`) rather than engine-generated, and
  why multi-move puzzles were left out of scope (TD-019).
- `GET /games/{id}` returns `moves: {uci, san, move_number}[]` and **no per-ply FEN**,
  so the backwards loader replays them forward from the opening with `forwardFens`
  (chess.js) — the same FEN-forward walk the server and `lib/game-events.ts` already
  do — then steps the list in reverse.
- A `NULL` `slot_key` never dedupes under Postgres, so gameless awards need a
  **partial** unique index (`… WHERE slot_key IS NOT NULL`) while the existing
  `uq_point_award_slot` keeps guarding game awards.

**Shipped this session — backend (`app/training/`).**
- `drills.py`: 18 frozen-dataclass drills, 6 themes × 3 levels. `verify.py` returns a
  problem string per drill; `verify_all()` is called both by a test and by
  `scripts/check_drills.py`, so an unsound drill fails CI.
- `from_reviews.py`: `mine_puzzles` reads the caller's `completed` reviews, keeps hero
  mistake/blunder plies with `centipawn_loss ≥ MINE_MIN_LOSS_CP (120)` and a legal
  `best_uci`, keys them `mine:{game}:{ply}`, dedupes on `(fen, best_uci)`. No content
  is invented — every puzzle is a position the player actually faced.
- `service.py`: `next_level` (+1 on three correct, −1 on two consecutive wrong),
  `summary`, `next_puzzle` (**never** serialises `solution`/`alternatives`/`line`),
  `record_attempt` (illegal uci → `422`; solved on first solve awards `drill`=2 and,
  for a non-`missed` theme's first clear, `theme_clear`=5) and `reveal` (no credit).
- Migration `e2a9c4f1b830` (revises `d7f3b0c9e512`): `training_attempts` table, plus
  `point_awards.game_id` → nullable and `slot_key` + partial unique index; the
  `award_points` insert body was extracted into `_record` with a new `award_ledger`
  wrapper (all 8 existing call sites untouched).
- Achievements: `_training_stats` (`puzzles_solved`, `drill_streak`) and a `training`
  group with the **Puzzle Solver** and **Sharp Streak** ladders.
- API `app/api/v1/training.py` (registered in `main.py`): `GET /training/summary`,
  `GET /training/puzzle`, `GET /training/mine`, `POST /training/attempts` (`_SameOrigin`).

**Shipped this session — frontend.**
- `LearnPage.tsx` at `/learn` (route + "Learn" `NavLink`): skill-card grid → drill
  panel reusing `Chessboard status="active"` (so legal-target dots work) → "From your
  own games" strip linking each mined puzzle back to its review; verdict, `why` and
  continuation come entirely from the server, achievements ride the response.
- `ReviewThinking.tsx`: a disabled board that steps `positions` in reverse every
  `REVERSE_STEP_MS = 450`, loops at the opening, falls back to a static start board on
  an empty/failed fetch, and `clearInterval`s on unmount; `ReviewPage`'s loading branch
  now renders it inside the card.
- Pure helpers in `lib/training.ts` (`levelChip`, `progressPct`, `themeOrder`,
  `themeIdea`, `uciFromTo`), `forwardFens`/`isCheck` in `lib/chess.ts`, four methods on
  `api-client.ts`, mirrored types, `training` group label/icon, and the learn +
  review-thinking styles.

**Defects found and fixed while verifying.**
- `alembic check` on a fresh scratch DB **failed**: the migration had created
  `ix_training_attempts_game_id`, which the model never declares (only `user_id` is
  indexed). Removed that index from the migration; the check is now clean — caught by
  the CI-order gate, not by eye.
- The ramp test asserted level 2 after solving mate-1/2/3 but got 3: `_level_from`
  reads the last attempt's stored level, so climbing three different drills leaves the
  base at 3. Fixed the test to re-solve mate-1 (level 1) three times.
- `Chessboard` selection is parent-controlled; `LearnPage` first passed a fixed
  `selected={null}`, so a click never fired. Added local `selected` state +
  `onSelect`, reset when a puzzle opens.
- Two `setState`-in-effect lint errors (`ReviewThinking`, `LearnPage`) fixed with the
  render-time cursor guard and by keeping state writes inside promise callbacks.
- `styles.css` referenced an undefined `var(--border)` → the token is `var(--rule)`;
  a `forwardFens` test asserted a full FEN but chess.js omits the en-passant field
  when none is legal, so it now asserts placement + side-to-move.

**Live verification.** After `docker compose up -d --build` (the api container ran
`alembic upgrade head` and the docker DB moved `d7f3b0c9e512 → e2a9c4f1b830`),
against a seeded user + session over `curl` (a cookie-less non-browser client passes
the same-origin check): `GET /training/puzzle?theme=mate` returned the mate-1 FEN with
**no `solution`/`alternatives`/`line`** keys; the wrong-but-legal `a1a7` gave
`solved:false, points_awarded:0` and still revealed `Ra8#`; the correct `a1a8` gave
`solved:true, points_awarded:7` (2 drill + 5 first-theme-clear) riding four unlocks
including the two `training` ones (`First Solve`, `Warming Up`); `GET /training/summary`
showed `mate {solved 1, attempts 2, pct 0.3333}`, `puzzles_solved 1`, `streak 1`;
`GET /training/mine` was `[]`; an unauthenticated puzzle request was `401`. Seed rows
deleted afterwards.

**Tests & gates.** Backend **344 → 382** pytest (`test_training_drills.py` incl.
`verify_all()` soundness across all 6 themes, `test_training_api.py` for the
answer-free payload / verdict / ramp / ledger / unlocks, `test_training_mine.py`, and
four gameless ledger rows in `test_points.py`; four paths in `test_openapi.py`).
Frontend **207 → 236** vitest (20 files): `ReviewThinking.test.tsx` (fake timers,
`getTimerCount()` proving the interval is cleared), `training.test.ts`,
`LearnPage.test.tsx`, `forwardFens` cases, and a `ReviewPage` loading-branch test; the
19 original `ReviewPage` tests still pass unchanged. Gates in CI order: `ruff check
app tests scripts`, `ruff format --check app tests`, `mypy app` (73 files),
`alembic upgrade head` + `alembic check` on a fresh scratch DB ("No new upgrade
operations detected"), `pytest`, `npm run lint`, `tsc --noEmit`, `test:run`,
`vite build`, `prettier --check src` — all green.

**Decisions & tracking.** Architecture **D12** (drills hand-authored and re-proved by
python-chess at test time; the server is the only place a solution is known) and a
`training` module row; new debt **TD-019** (pattern soundness cannot detect a quieter
alternative move). `PROJECT_CHECKLIST.md`: **REV-005 ticked**, **TAC-001/002** marked
partial, a new **Stage 6 — Learning** with **LEARN-001..006** ticked, and the Phase 10
gate counts refreshed. `docs/api.md` gains the Training section (four routes, the
answer-free rule, points/reveal semantics).

**Remaining / next task.** A human browser pass on `/learn` (the drill board feel and
the backwards review loader on a real screen — jsdom asserts behaviour, not pixels) and
on the voice/animation quality; TD-019's engine-verified catalog regeneration if a
player reports a good move marked wrong; a generic tactics detector to fully close
TAC-001/002 (the drill themes name the patterns but no over-the-board scan exists yet).

---

## Session 2026-10-24 (r) — Learn: 300+ verified drills, two new themes, board sizing

**Goal.** Two follow-ups to the Learn section: grow the drill catalog well past **300**
positions, and shrink the animated review loader (and the `/learn` drill board) to the
same footprint as the in-play board. Chosen approach for the expansion: generate
positions from parametric templates and keep only what the existing soundness prover
accepts — "generate + auto-verify" — and add two new themes for variety.

**Board sizing (`web`).** The play board is capped by `.board-frame`
(`width: min(100%, calc(100dvh - 16rem)); max-width: 46rem; margin: 0 auto`) and its
pieces scale with `cqw` off `.board-wrapper`, so the wrapper must be capped — not the
`.board` — to keep piece sizes right. `ReviewThinking.tsx` now wraps `<Chessboard>` in
`<div className="board-frame">`; `LearnPage.tsx`'s drill board is `drill-board
board-frame`. `13` loader/Learn tests pass.

**Generated catalog (`api/training`).** New `app/training/generate.py` builds each theme
from geometric templates — back-rank/smothered **mate**, undefended-piece **hanging**,
knight-fork-of-king-and-target **fork**, rook-pinned-piece **pin**, and two new themes:
**skewer** (a rook slide checks the king, the king steps off the line, the rook takes the
piece behind it) and **discovered** (a piece captures while vacating a file to uncover
the rook's check). Every candidate is run through `verify.verify()` before it is kept,
with motif guards in the generator on top (hanging square undefended, real `is_pinned`,
check-then-capture for skewer/discovered). The catalog composes as
`DRILLS = CURATED + generated_drills()` — curated **first**, so the ramp and
`test_puzzle_payload_has_no_answer` still resolve a fresh mate theme to `mate-1`. Keys
are deterministic (`gen-{theme}-{level}-{n}`, fixed square iteration + a per-(theme,
level) cap of 16). Import + generation cost ~0.3s.

**Theme wiring.** `skewer`/`discovered` added to `THEME_NAMES`/`THEME_ORDER`
(`drills.py`) and `_MATERIAL_THEMES`/`VALID_THEMES` (`verify.py`), so they are proved by
the durable-material-gain path. Frontend `lib/training.ts` gains their card order and
teaching lines. `service.summary`/`next_puzzle` needed no change — they key off
`THEME_ORDER`/`DRILLS`.

**Catalog result: 351 verified drills, 8 themes, every theme covering levels 1-3.**
`mate 39 · hanging 51 · fork 51 · pin 51 · skewer 39 · discovered 48 · backrank 33 ·
endgame 39`. `verify_all(DRILLS) == []`.

**Tests.** `test_training_drills.py` now asserts `len(DRILLS) > 300` and folds
`skewer`/`discovered` into the material-gain test; `training.test.ts` locks the 8-theme
order and the new teaching lines. Backend **382** pytest (count unchanged — assertions
retuned, not added), frontend **236** vitest.

**Gates (CI order).** `ruff check app tests`, `ruff format --check app tests`, `mypy app`
(74 files), `pytest` — green; frontend `npm run lint`, `tsc --noEmit`, `test:run`,
`vite build`, `prettier --check src` — green; `scripts/check_drills.py` reports "All 351
drills are sound." No migration was needed (the catalog is code, not schema), so the
alembic gate is untouched. After `docker compose up -d --build`, live `curl` as a freshly
registered user: `GET /training/puzzle?theme=skewer` and `?theme=discovered` return
`gen-skewer-1-0`/`gen-discovered-1-0` with **no answer keys**; `POST` the correct
`mate-1` move still awards `7` (curated-first preserved); a generated `gen-skewer-1-0`
solve graded `solved:true, points 7` and revealed the forced continuation `Kb4 Rxa5`;
`GET /training/summary` lists all 8 themes with the new labels (Skewers, Discovered
Attacks). Test rows deleted afterwards.

**Docs.** `PROJECT_CHECKLIST.md` LEARN-001/006 refreshed; `docs/api.md` Training intro
and puzzle row now say 8 themes / 351; `docs/architecture.md` `training` module row and
**D12** reworded for the template-generated, verify-filtered catalog; **TD-019** notes
generated positions pass the same pattern prover.

**Remaining / next task.** Human browser pass to eyeball the resize and the new-theme
cards; TD-019's engine-verified regeneration if a player reports a co-win marked wrong
(the pattern prover accepts only the drill's own move, which now governs hundreds of
generated positions).

---

## Session 2026-10-24 (s) — Learn: multi-move `sequence` puzzles + catalog to 829

**Goal.** Two deliverables: (A) a new `sequence` theme of multi-move puzzles solved by
playing a whole forced line, graded by exact-line replay; (B) grow the drill catalog by
**400+** verified positions, taking the total past 750.

**Data model (no migration).** `drills.py`: one new field on the frozen `Drill`,
`moves: tuple[str, ...] = ()` — a `sequence` drill's full player-first alternating line
(odd length); `solution` mirrors `moves[0]` so single-key resolution still works, and
`player_moves = (len(moves)+1)//2`. Added the 9th theme name ("Multi-Move Puzzles") and
appended `sequence` to `THEME_ORDER`.

**Verification.** `verify.py`: `_verify_sequence(drill, board)` replays the whole line
from the start FEN and requires (i) every ply legal, (ii) every **opponent** ply to have
exactly one legal move (the forced reply) — this is what makes the material/mate claim
sound without an engine, (iii) no premature mate/stalemate before the final player ply,
and (iv) a terminal that is checkmate or nets `>= MIN_GAIN_CP`. Routed via the
`_SEQUENCE_THEMES` branch in `verify()`.

**Generation.** Import must stay fast, so multi-move lines are **authored offline** and
embedded as `_SEQUENCE_SEEDS` (120 certified forced-mate seeds across 3 levels), then
re-certified by `verify()` at import (the safety net prunes any bad entry). A FEN dedup
in `_sequence_drills()` (exact-line replay needs one line per board) lands **65** sequence
drills (L1 27 / L2 29 / L3 9). Raised `_CAP` 16 → 48 for the large-geometry single-move
families; `verify()` still prunes unsound candidates so quality is unchanged. All shipped
sequence content is forced mates; forced-material sequences are the verifier-supported
remaining case, left as future work.

**Catalog result: 829 verified drills, 9 themes** (up 458 from 351), import ~0.30s,
`verify_all(DRILLS) == []`, `scripts/check_drills.py` reports "All 829 drills are sound."

**Grading (stateless, exact-line).** `service.py`: kept `record_attempt` byte-for-byte and
added `record_sequence_attempt(db, user_id, key, played)` — replays cumulative player
moves with the scripted forced replies; illegal → `IllegalAttemptError` (422);
legal-but-wrong → one failed attempt row + reveal, `complete:true`; full correct line →
one solved row (`uci = moves[-1]`) + reveal, `complete:true`; correct-but-unfinished →
logs nothing, returns `complete:false` + `position_fen` + `played_san` so the client
advances the board. `schemas.py`/`training.py`: `PuzzleResponse.player_moves`,
`TrainingAttemptRequest.moves`, `TrainingAttemptResponse.{complete, position_fen,
played_san}`; the router branches to `record_sequence_attempt` on a non-empty `moves`.

**Frontend.** `api-types.ts` mirrors the new optional fields; `training.ts` adds
`sequence` to `THEME_SEQUENCE` + a `THEME_IDEAS` line; `LearnPage.tsx` runs a stepper
(local `played` + `currentFen`, "Move X of Y" progress line) driving the parent-controlled
board; `styles.css` gains `.drill-progress`.

**Tests & gates.** Backend: `test_training_drills.py` count assertion raised to
`len(DRILLS) > 750` + a new `test_every_sequence_drill_forces_a_win` (replays every
sequence, asserting legality, forced replies, no premature resolve, terminal
mate-or-gain). `test_training_api.py` gained 5 sequence tests (no-answer move count,
in-progress logs nothing, full line = one row with points, wrong ply fails+reveals,
illegal ply 422). Frontend: `training.test.ts` 9-theme order + `themeIdea('sequence')`;
`LearnPage.test.tsx` a two-ply stepper-to-solve test. Backend ruff format/check + mypy
clean; 31 backend + 18 frontend training tests green.

**Docs.** `docs/architecture.md` **D12** reworded (multi-move now in scope via
generation-time forced-line certification; grade-time is exact-line/deterministic; no
engine) and the `training` module row updated; **TD-019** notes the exact-line limit now
applies per ply to sequences; `docs/api.md` Training section says 9 themes / 829 and
documents `moves`/`player_moves`/`complete`/`position_fen`/`played_san`;
`PROJECT_CHECKLIST.md` LEARN-001 refreshed and a new **LEARN-007** ticked (Phase 10 →
32 items).

**Remaining / next task.** Human browser pass on `/learn` to eyeball the sequence stepper;
forced-material sequence generation (the verifier already accepts a gain terminal) and
TD-019's engine-verified alternative-defence widening if a player reports a co-win marked
wrong.

---

## Session 2026-10-24 (t) — Phase 11: Engine-grounded Coach Assistant (the ⭐)

**Task.** Build the conversational coach reached from a ⭐ to the left of "Where to
improve" on the review page. It answers five things — the positions, the best way to
proceed, other ways the game could have gone (long-context over the stored review + a
bounded live-MultiPV what-if pass), what the player keeps doing wrong across games, and
opening theory (Postgres full-text RAG over a `coach_index` projection + the offline
book). No pgvector/embeddings. An OpenAI-compatible LLM is optional, env-gated, and only
rephrases cited facts behind a cite-only grounding guard with a deterministic fallback.

**Files changed.**
- Backend new: `app/ai/` (`provider.py`, `compose.py`, `service.py`), `app/ai/longcontext/`
  (`context.py`, `whatif.py`), `app/ai/rag/` (`models.py`, `index.py`, `recall.py`),
  `app/api/v1/assistant.py`, migration `alembic/versions/f6b1c8d2a9e4_coach_index.py`,
  `scripts/index_reviews.py` (backfill), `app/ai/docs/*` (README/architecture/plan/checklist + SVG).
- Backend edits: `core/database.py` (assistant_*/coach_* settings), `models/__init__.py`
  (`CoachIndex`), `api/v1/{schemas,deps,main}.py`, `reviews/service.py` (best-effort
  `index_review_safe` hook).
- Frontend: `lib/api-types.ts` + `lib/api-client.ts` (`askCoach`/`coachPatterns`),
  `components/CoachAssistant.tsx` (+ test), `pages/ReviewPage.tsx` (⭐ toggle), `styles.css`.
- Docs: `docs/architecture.md` (D13 + `ai` module row), `docs/api.md` (Coach assistant),
  `PROJECT_CHECKLIST.md` (Phase 11), `.env.example` (coach block), `TECHNICAL_DEBT_REGISTER.md`
  (deferred semantic recall), `.github/workflows/ci.yml` (coach CI coverage).

**Tests executed.**
- `pytest tests/ai` → 40 passed; full `pytest` → **428 passed**; `ruff check/format app tests
  scripts` clean; `mypy app` clean (86 files); `alembic upgrade head` + `alembic check` clean;
  migration **round-trip** (upgrade→downgrade base→upgrade) verified on a throwaway DB.
- Frontend `vitest run` → **243 passed** (5 new `CoachAssistant`, 1 new `ReviewPage` ⭐ test);
  `tsc --noEmit`, `eslint`, `prettier --check`, `vite build` all clean.

**Results.** The coach answers every intent offline: with no `ASSISTANT_API_KEY` and no
engine binary the deterministic path returns grounded, cited answers; the FTS index and
pattern recall were exercised against a real Postgres (generated `tsvector` column + GIN),
and `to_tsvector('english', …)` confirmed IMMUTABLE on PG14 so the stored generated column
is legal without any extension.

**Defects discovered.** The new CI migration round-trip exposed a **latent pre-existing
bug**: `a1c7e4f9b2d6_online_players.py` called `op.drop_constraint(..., exists=True)`, which
raises `TypeError` on any `alembic downgrade` (no such kwarg). CI never caught it because it
only ran `upgrade head`. Fixed by relying on PostgreSQL's automatic FK-with-column drop.

**Decisions made.** D13 — long-context + Postgres-FTS RAG, no new dependency, optional LLM
behind a cite-only guard; embeddings/pgvector deferred as the growth path.

**Remaining / next task.** COACH-I4: a manual live-Docker curl through each intent on a real
reviewed game (scoping/rate-limit/404 already proven by HTTP tests); optional semantic recall
later if keyword FTS under-serves phrasing variety.

---

## Session 2026-10-25 — Phase 11b: Conversational coach upgrade (memory + board walks)

**Task.** Make the ⭐ coach genuinely engaging: (1) richer multi-section teaching answers
(the move, the idea, the line, why it beats the alternative); (2) real conversation memory
so follow-ups like "and after that?" / "show me the line" resolve against the prior focus
and intent; (3) the coach drives the **main review board** through a grounded multi-move
variation. Hard invariants preserved: every named move traces to a stored ply / live engine
PV / book; no new dependency; no DB migration (lines computed on read); tests/CI offline.

**Files changed.**
- Backend new: `app/ai/longcontext/lines.py` (`LineStep`, `best_alt`, `played_line`,
  `engine_line`, `line_from_alt`).
- Backend edits: `longcontext/whatif.py` (`AltLine.pv_uci`), `compose.py` (LESSON/WHY/IDEA
  intents, multi-section `_plan/_alternatives/_why/_idea/_lesson`, `Composed.line`/`line_title`,
  `_line_and_title`), `service.py` (`history` + focus carry-forward `_resolve_focus_ply`,
  warm conversational `_SYSTEM_PROMPT`/`_llm_prompt`, `CoachAnswer.line`), `core/database.py`
  (`coach_history_max_turns`, `coach_line_max_steps`), `api/v1/schemas.py`
  (`CoachHistoryTurn`, `AssistantLineStep`, `history`/`line`/`line_title`), `api/v1/assistant.py`.
- Frontend: `lib/api-types.ts` (+`CoachHistoryTurn`/`AssistantLineStep`/`line`/`line_title`),
  `components/CoachAssistant.tsx` (send history, multi-line render, "Show this line",
  suggestion chips, autoscroll), `pages/ReviewPage.tsx` (lesson state drives the board +
  stepper + autoplay + exit), `styles.css`.
- Docs: `app/ai/docs/checklist.md` (Phase 11b block), `docs/architecture.md` (D13 extended),
  `docs/api.md` (history/line/line_title/new intents), `PROJECT_CHECKLIST.md`.

**Tests executed.**
- New `tests/ai/test_lines.py` (played-line stitching + FEN chaining, engine-line truncation,
  offline fallback); `tests/ai/test_context_compose.py` (+new-intent routing, plan/lesson carry
  a walkable line); `tests/ai/test_assistant.py` (+follow-up focus carry-forward, HTTP lesson
  returns a line, offline PLAN still yields a line). `pytest tests/ai` → **52 passed**.
- Frontend: `CoachAssistant.test.tsx` (history sent, multi-line render, onPlayLine) and
  `ReviewPage.test.tsx` (lesson drives the board to the step FEN + exit restores the game
  cursor); `tsc --noEmit` clean.

**Results.** The coach gives structured, walkable teaching entirely offline: with no engine
and no key, `line_from_alt` degrades to the recorded plies so there is always a truthful
variation to step through, and the cite-only `grounded()` guard is untouched — an LLM can
phrase but never invent. No schema change; the line is derived at read time.

**Decisions made.** Extend D13 (11b): walkable lines from the two honest sources, bounded
conversation memory with focus carry-forward, main-board lesson overlay — all reversible.

**Remaining / next task.** Live-Docker sign-off of the board walk (a real reviewed game, then
"show me a better line" → the big board steps it; "and after that?" continues the thread).

## Session 2026-10-25 (b) — Phase 12A: Observability + cost-tiered rate limiting (D14/D15)

**Task.** Market-readiness stage 12A of `docs/market-plan.md`: give the service eyes
(JSON logs + Prometheus) and a shield (cost-tiered limiters + a hosted-engine budget
guard) before any public release. Triggers: the review surface holds a warm engine ~12 s
per call and was unlimited; the shared stockfishapi.com free tier is 2,000 units/day for
the whole account; deployment.md §8 still said "metrics to wire".

**Files changed.**
- Backend new: `app/core/telemetry.py` — logging setup (`LOG_JSON`, default JSON lines
  `{ts, level, logger, msg, request_id?, http?, exc?}`; no secrets/tokens ever, QA-019),
  the six bespoke instruments (`engine_analyse_seconds{provider}`,
  `engine_unavailable_total`, `rate_limit_rejections_total{bucket}`,
  `cloud_units_used_today`, `cloud_upstream_errors_total{status}`, `ws_connections_active`),
  and the request-id middleware (honors inbound `X-Request-ID`, echoes it back).
- Backend edits: `app/main.py` (instrumentator mounts `/metrics`; middleware order),
  `api/v1/deps.py` (RL-001..004: review limiter 10/h/user with `force` costing 2,
  training limiter 60/min/user, `Retry-After` on every 429 from all buckets,
  rejection counter per bucket), `engine/cloud_stockfish.py` (RL-003 + MON-006: app-wide
  daily-unit guard tripping at `CLOUD_DAILY_UNIT_BUDGET` (1,800) with a clean 503 before
  upstream 429/402 does; 0 disables; upstream 4xx counted by status), `engine/factory.py`
  + `games/opponent.py` + `reviews`/`whatif` call sites (MON-003/004 observed where
  analyses run and failures surface — the factory deliberately does not increment, to
  avoid double-counting), the online ws hub (MON-007 gauge), `core/database.py` (new
  settings), `pyproject.toml` + `requirements.lock` (`prometheus-fastapi-instrumentator==8.1.0`,
  `prometheus-client==0.26.0`).
- Docs: new `docs/market-plan.md` (Phase 12 tracker, 12A checked off); D14–D17 in
  `docs/architecture.md`; TD-021/022/023 filed; `PROJECT_CHECKLIST.md` Phase 12 stage;
  deployment.md §7–§8 rewritten from "to wire" to what exists + alert-target list;
  `docs/api.md` 429/`Retry-After` + `/metrics` semantics; `.env.example` new knobs
  (`REVIEW_RATE_LIMIT_PER_HOUR`, `TRAINING_RATE_LIMIT_PER_MINUTE`,
  `CLOUD_DAILY_UNIT_BUDGET`, `LOG_JSON`).

**Tests executed.**
- New `tests/test_phase12_telemetry.py`: `/metrics` serves Prometheus text and stays out
  of the OpenAPI contract; `X-Request-ID` honored/echoed; JSON log line shape; review
  budget (11th in the hour → 429 + `Retry-After`, a `force` re-run costs 2); training
  limiter; rejection counter moves. Cloud-budget tests appended to
  `test_cloud_stockfish.py`. Full suite `pytest` → **460 passed** (up from 428 pre-12A).
- Gates in CI order: `ruff check` + `ruff format` clean (127 files), `mypy app` success
  (88 files), `alembic upgrade head` + `alembic check` clean on a fresh throwaway DB
  ("No new upgrade operations"), frontend eslint/`tsc` clean, vitest **247 passed**
  (21 files), `vite build` ok, prettier clean (3 Phase-11b files reformatted).

**Results.** `/ready` + `/metrics` + JSON request-traceable logs give the ops floor D14
promised; every expensive surface now has a budget, and the cloud pot can no longer be
burned dry by one route — the guard trips locally before upstream does. No schema change;
limiters stay in-process (swap to Redis is RL-005, triggered by TD-012).

**Decisions made.** D14 (observability via Prometheus text + JSON logs, no hosted APM at
launch) and D15 (cost-tiered limiters: hourly on engine-holding surfaces, per-minute
elsewhere, `force` costs double, global cloud budget) implemented as planned; engine
failure counted where it surfaces, never at the factory seam.

**Remaining / next task.** Stage 12B (identity + minimal RBAC: SEC-021..028) and 12C-C1
capture tables (FP-001..003) per `docs/market-plan.md`; RL-005 Redis swap only when
TD-012 trips; TD-021 (proxy/XFF trust) must land before real-IP limiting behind a
reverse proxy.

## Session 2026-10-25 (c) — ElevenLabs TTS: "works on Linux, silent on Mac" diagnosis

**Task.** The user reported the ElevenLabs voice (PR #13, merged to main) narrating on
their Linux box but not on this Mac, and asked to check the implementation. Reproduced
end-to-end against the live `chessnginc-api-1` container.

**Root cause (not a code bug).** The feature is fully wired and correct: `.env` key →
compose forwards `elevenlabs_api_key/voice_id/model_id` → running container sees them →
`app/api/v1/tts.py` proxies `POST /api/v1/tts` → ElevenLabs. Direct provider call
returns **401 `authentication_error / missing_permissions`: "The API key you used is
missing the permission text_to_speech"**. The key authenticates but its scope lacks the
TTS permission. The proxy maps 401→502, and `voice.ts::fetchTTSAudio` treats non-503
non-ok as `'error'` → silent browser-speechSynthesis fallback — hence a robotic voice
here vs the premium voice on Linux (that box's `.env` holds a differently-scoped key;
`.env` is gitignored, so the two machines legitimately differ).

**Fix for the user (outside the repo).** In the ElevenLabs dashboard, edit the API key
`sk_430be9…` and tick the **text_to_speech** permission (or mint a key that has it),
put it in the root `.env`, then `docker compose up -d api` to recreate with the new
value. No code change is needed for the voice to work.

**Code change made (diagnosability only).** `app/api/v1/tts.py` 401 branch: the old
message "rejected credentials" was misleading (the key is valid, the scope is not).
It now logs the provider's detail server-side (never echoes the key) and returns an
accurate hint to verify the key is granted `text_to_speech`, so a future
per-machine key difference is self-evident instead of looking like a broken build.

**Tests executed.** `pytest tests/test_tts.py` → **10 passed** (401→502 mapping asserts
status only, unaffected). `ruff format`/`ruff check`/`mypy` clean on the changed file.

## Session 2026-10-25 (d) — Multi-voice narration + AI-coach voice (opt-in consent)

**Task.** "Implement several free voices" and let the user authorize the voice in the
AI coach. Prior state: one hardcoded ElevenLabs voice, narration only on the review
tour, no way to pick a voice, no coach speech, no per-user persistence.

**Design (confirmed with the user).** Two voice families in one picker (browser OS
voices + a curated free-tier ElevenLabs catalog), an explicit opt-in that authorizes
the coach to speak its answers, and server-side per-user persistence so the choice
follows the account.

**Backend.**
- `app/models/user.py`: `voice_authorized` (Bool, default False) + `voice_id` (Str(64),
  default "") on `users`; migration `b4e2d7c0a915` (revises `f6b1c8d2a9e4`) adds both
  with a server default to backfill existing rows, then drops the default so the schema
  matches the ORM's Python-side default (`alembic check` clean).
- `app/api/v1/tts.py`: `FREE_ELEVEN_VOICES` allowlist (Rachel/Adam/George/Daniel) is the
  single source of truth — the only ids ever accepted from a client or interpolated into
  the provider URL. `GET /tts/voices` lists them with an `available` flag (false with no
  key). `POST /tts` gains an optional `voice` field, validated against the allowlist
  (`400` otherwise). Authenticated `GET/PUT /me/voice` read/write the consent + selection;
  an ElevenLabs id is allowlist-checked on write, a browser voice name is stored as a
  harmless preference string (the `/tts` path independently guards the real call).
- `schemas.py`: `VoiceOption`/`VoiceListResponse`/`VoicePreferencesResponse`/`VoicePreferencesUpdate`.

**Frontend.**
- `api-client.ts`: a `put` helper + `listVoices`/`getVoicePrefs`/`saveVoicePrefs`; `api-types.ts` voice types.
- `voice.ts`: a session-wide `VoiceSelection` (`{engine, id}`); `setVoiceSelection`/
  `getVoiceSelection`/`listBrowserVoices`. `speak()` with a browser selection never
  touches the proxy; an ElevenLabs selection forwards its id and re-arms the probe; a
  null selection keeps the original default-then-fallback behaviour.
- `CoachAssistant.tsx`: a voice bar (consent checkbox + a `<select>` grouping browser
  then premium voices, unavailable ones disabled); hydrates prefs + catalog on mount and
  degrades quietly offline; speaks an answer **only when `voice_authorized`**, persists
  consent/pick changes.

**Tests.** Backend `pytest tests/test_tts.py` → **20 passed** (catalog, allowlist reject,
`/me/voice` roundtrip incl. PUT, TTS `voice` param). Frontend: `CoachAssistant.test.tsx`
voice suite (5 cases: silent-unless-authorized, speaks-when-authorized, consent persists,
catalog pick forwards to selection+storage, unavailable voice disabled) → **13 passed**
in the file; `voice.test.ts` unaffected.

**Gates (CI order, all green).** ruff check/format, mypy (89 files), alembic
upgrade-head + check on a clean throwaway DB, `pytest` **480 passed**; frontend eslint,
`tsc --noEmit`, `vitest` **252 passed**, `vite build`, prettier.

**Docs.** `docs/api.md` new *Voice & narration* section (endpoints, allowlist trust
boundary, 503/fallback semantics, opt-in default).

**Remaining / next task.** Nothing blocking; the premium catalog voices only actually
play once an ElevenLabs key carrying the `text_to_speech` scope is set (see session (c))
— until then every pick falls back to the browser voice.






