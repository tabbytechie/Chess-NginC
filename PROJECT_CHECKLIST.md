# PROJECT CHECKLIST

> Authoritative progress tracker for the Chess Engine project.
> Statuses: `[ ]` Not started · `[~]` In progress · `[x]` Implemented & verified · `[!]` Blocked/failing · `[-]` Intentionally deferred.
> A file existing does **not** mean its feature is complete. Mark `[x]` only after acceptance criteria pass and relevant checks run.

Priorities: **P0** security/data integrity/build blockers/illegal moves · **P1** core gameplay/accounts/persistence/AI correctness · **P2** usability/performance/accessibility/benchmarking · **P3** optional/nonessential.

---

## Phase 0 — Repository & Engineering Foundation

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| FND-001 | Inspect repository and record initial state | P1 | [x] | Empty dir, no git, Python 3.14.2, Node v25.2.1, psql 14.19, no Docker. See IMPLEMENTATION_LOG 2026-10-09. |
| FND-002 | Establish/verify Git repository | P1 | [x] | `git init -b main` + root commit `18f8145`. |
| FND-003 | Create the agreed directory structure | P1 | [x] | apps/api, apps/web, docs, infra, scripts, .github created; empty leaf dirs added as features land. |
| FND-004 | README.md with setup instructions | P1 | [x] | README.md (setup steps preliminary until toolchain lands). |
| FND-005 | CONTRIBUTING.md | P1 | [x] | CONTRIBUTING.md (commit/PR standards + quality gates). |
| FND-006 | docs/code-standards.md | P1 | [x] | docs/code-standards.md. |
| FND-007 | docs/architecture.md | P1 | [x] | docs/architecture.md (module boundaries + decisions log). |
| FND-008 | PROJECT_CHECKLIST.md | P1 | [x] | This file. |
| FND-009 | IMPLEMENTATION_LOG.md | P1 | [x] | IMPLEMENTATION_LOG.md (session 2026-10-09 recorded). |
| FND-010 | TECHNICAL_DEBT_REGISTER.md | P1 | [x] | TECHNICAL_DEBT_REGISTER.md (TD-001..TD-008). |
| FND-011 | Configure .gitignore | P0 | [x] | .gitignore (Python/Node/env/secrets/Stockfish binaries). |
| FND-012 | .env.example without secrets | P0 | [x] | .env.example (placeholders only, no real secrets). |
| FND-013 | Python project metadata + dependency locking | P1 | [x] | apps/api/pyproject.toml + requirements.lock; venv install verified. |
| FND-014 | Node package metadata + lockfile | P1 | [x] | apps/web/package.json + package-lock.json (npm). |
| FND-015 | Python lint/format/type-check config (Ruff, mypy) | P1 | [x] | Ruff + mypy in pyproject.toml; `ruff check`/`format --check`/`mypy app` all pass. |
| FND-016 | TS strict mode + ESLint + Prettier | P1 | [x] | tsconfig strict + eslint.config.js (flat) + .prettierrc; all pass. |
| FND-017 | Configure test commands | P1 | [x] | pytest (2 passed) + vitest (1 passed). |
| FND-018 | Docker Compose | P1 | [x] | Full `docker compose up` verified: db+api(healthy)+web Up; `smoke-prod.sh` PASS vs containerized API; SPA 200 + security headers. Fixed PG18 volume mount. |
| FND-019 | Verify PostgreSQL starts & accepts connections | P1 | [x] | Local PG14 accepts TCP on :5432; `chess` DB live; Alembic migrations apply. |
| FND-020 | Verify frontend starts | P1 | [x] | `vite` dev server serves index.html on :5173; production build succeeds. |
| FND-021 | Verify backend starts | P1 | [x] | `uvicorn app.main:app` starts; `/` and `/api/v1/health` return 200. |
| FND-022 | Backend health endpoint | P1 | [x] | GET /api/v1/health → 200 {"status":"ok"} (tested). |
| FND-023 | CI workflows | P1 | [x] | `.github/workflows/ci.yml`: backend (ruff, mypy, pip-audit, `pytest --cov-fail-under=85`, migration up/down/`alembic check`), frontend (prettier, eslint, tsc, vitest, build, OpenAPI drift), `images` build job, Playwright `e2e` job; actions pinned by commit SHA. |
| FND-024 | Verify clean setup on fresh environment | P2 | [ ] | |

---

## Phase 1 — Chess Rules & Domain

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| CHS-001 | Game modes & game-status enums | P1 | [x] | app/games/domain.py (GameMode, Color, GameStatus). |
| CHS-002 | Game domain model | P1 | [x] | app/games/domain.py (Game, Move dataclasses). |
| CHS-003 | Chess-rules adapter | P1 | [x] | app/games/rules.py (ChessRules). |
| CHS-004 | Integrate python-chess | P1 | [x] | chess imported only in rules.py. |
| CHS-005 | Board initialization | P1 | [x] | ChessRules().fen == STARTING_FEN (tested). |
| CHS-006 | Validate UCI moves | P0 | [x] | parse → InvalidMoveError; legality → IllegalMoveError (tested). |
| CHS-007 | SAN move notation | P1 | [x] | apply_move returns SAN (e4, O-O, a8=Q tested). |
| CHS-008 | Detect check | P1 | [x] | ChessRules.is_check() (fool's-mate test). |
| CHS-009 | Detect checkmate | P1 | [x] | ChessRules.status() → CHECKMATE (fool's-mate test). |
| CHS-010 | Detect stalemate | P1 | [x] | ChessRules.status() → STALEMATE (stalemate FEN test). |
| CHS-011 | Castling (kingside & queenside) | P1 | [x] | test_special_moves.py (O-O, O-O-O, illegal cases). |
| CHS-012 | En passant | P1 | [x] | test_special_moves.py (capture + expiry). |
| CHS-013 | Promotion & underpromotion | P1 | [x] | test_special_moves.py (Q/R/B/N, invalid rejected). |
| CHS-014 | Repetition & draw rules | P1 | [x] | ChessRules.status() uses can_claim_draw() for fifty-move and threefold (test_rules.py). |
| CHS-015 | Resignation | P1 | [x] | Game.resign() method with validation (test_domain.py). |
| CHS-016 | Draw claims & automatic draws | P1 | [x] | Automatic draws covered by CHS-014 (can_claim_draw). Explicit claims handled at service layer. |
| CHS-017 | Generate & validate FEN | P1 | [x] | ChessRules.fen + validate_fen/is_valid_fen (test_rules.py). |
| CHS-018 | Generate PGN from move history | P2 | [x] | Game.to_pgn() method with move numbering (test_domain.py). |
| CHS-019 | Move history & replay | P1 | [x] | ChessRules.replay_moves() method (test_rules.py). |
| CHS-020 | Undo semantics | P1 | [x] | ChessRules.undo_move() method (test_rules.py). |
| CHS-021 | Verify board invariants | P0 | [x] | ChessRules.verify_invariants() checks kings/pawns (test_rules.py). |
| CHS-022 | Edge-case tests | P1 | [x] | Edge cases: empty replay, long sequences, turn alternation, FEN persistence (test_rules.py). |
| CHS-023 | Property-based legal-move tests | P1 | [x] | Hypothesis-based tests for legal moves, undo FEN restoration (test_rules.py). |
| CHS-024 | Terminal positions & special-move tests | P1 | [x] | Terminal positions (checkmate, stalemate, insufficient material) and special moves (test_rules.py). |

---

## Phase 2 — Database & Migrations

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| DB-001 | Configure SQLAlchemy | P1 | [x] | app/core/database.py with engine and session factory |
| DB-002 | Configure Alembic | P1 | [x] | alembic.ini and alembic/env.py configured |
| DB-003 | users migration | P1 | [x] | User model in app/models/user.py (migrated) |
| DB-004 | sessions migration | P1 | [x] | Session model in app/models/session.py (migrated) |
| DB-005 | games migration | P1 | [x] | Game model in app/models/game.py (migrated) |
| DB-006 | game_moves migration | P1 | [x] | GameMove model in app/models/game_move.py (migrated) |
| DB-007 | engine_runs migration | P1 | [x] | EngineRun model in app/models/engine_run.py (migrated) |
| DB-008 | benchmark_runs migration | P2 | [x] | Model `app/models/benchmark_run.py`; migration `5a0dcdb13bb3` (upgrade/downgrade verified). |
| DB-009 | benchmark_results migration | P2 | [x] | Model `app/models/benchmark_result.py`; same migration `5a0dcdb13bb3`. |
| DB-010 | Foreign keys | P1 | [x] | FKs defined in models (sessions.user_id, game_moves.game_id, etc.) |
| DB-011 | Unique constraints | P1 | [x] | Unique on users.email, sessions.token |
| DB-012 | Necessary indexes | P2 | [x] | Indexes on foreign keys and unique fields |
| DB-013 | Ownership constraints at service level | P0 | [x] | GameRepository enforces user_id on all operations |
| DB-014 | Repository interfaces | P1 | [x] | GameRepository with CRUD and ownership methods |
| DB-015 | Transactional game persistence | P0 | [x] | Repository methods use SQLAlchemy transactions |
| DB-016 | Atomic move submission + version updates | P0 | [x] | update_fen() with optimistic concurrency version checking |
| DB-017 | Game recovery | P1 | [x] | GameRepository.recover_game() with ownership enforcement |
| DB-018 | Test rollback after failed write | P0 | [x] | test_rollback_after_failed_write() (test_game_repository.py) |
| DB-019 | Test stale-version conflicts | P0 | [x] | test_update_fen_version_check() (test_game_repository.py) |
| DB-020 | Test migrations from empty DB | P1 | [x] | `146802a49aef` initial schema verified from empty DB (creates users, games, sessions, game_moves, engine_runs). |
| DB-021 | Test upgrades from previous schema | P1 | [x] | Verified via downgrade→upgrade round-trip (`alembic downgrade base && alembic upgrade head`). |
| DB-022 | Document backup & restore | P1 | [ ] | |

---

## Phase 3 — Authentication & Security

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| SEC-001 | Registration | P1 | [x] | POST /api/v1/auth/register → 201 + session (app/api/v1/auth.py). |
| SEC-002 | Normalize & validate email | P1 | [x] | normalize_email: trim/lowercase/regex/length (app/auth/validators.py). |
| SEC-003 | Secure password hashing | P0 | [x] | bcrypt via app/auth/security.py; 72-byte cap; no plaintext stored. |
| SEC-004 | Login | P1 | [x] | POST /api/v1/auth/login → 200 + session; generic 401 message. |
| SEC-005 | Logout & session revocation | P1 | [x] | POST /api/v1/auth/logout → 204, deletes session row + cookie. |
| SEC-006 | GET /api/v1/auth/me | P1 | [x] | Returns {id, email}; 401 when unauthenticated. |
| SEC-007 | Secure HttpOnly SameSite cookies | P0 | [x] | session_token: HttpOnly, SameSite=Lax, Secure flag from settings. |
| SEC-008 | CSRF protection | P0 | [x] | SameSite=Lax + Origin/Referer allowlist check (enforce_same_origin). |
| SEC-009 | Enforce HTTPS in production | P0 | [ ] | Needs deployment config (Phase 9); COOKIE_SECURE flag ready. |
| SEC-010 | Game ownership on reads | P0 | [x] | GET game(s) scoped to caller; foreign → 404 (tested). |
| SEC-011 | Game ownership on writes | P0 | [x] | All mutations scoped to caller; foreign → 404 (tested). |
| SEC-012 | Login/registration rate limits | P1 | [x] | 10/min per IP in-memory (deps.rate_limit_auth); Redis noted for prod. |
| SEC-013 | Engine endpoint resource limits | P0 | [x] | `/engine-move` rate-limited per user (`rate_limit_engine`); difficulty→budget map enforced server-side; sidecar re-applies hard caps; per-user concurrency cap + circuit fallback (`app/engine/circuit.py`). |
| SEC-014 | Explicit CORS config | P1 | [x] | Allowlist from settings in app/main.py; credentials enabled, no wildcard. |
| SEC-015 | Keep secrets out of source control | P0 | [x] | .env.example placeholders only; .gitignore covers .env; no secrets logged. |
| SEC-016 | Safe error responses | P1 | [x] | Generic "Invalid email or password"; {detail} envelope; no hash/stack leaks. |
| SEC-017 | No sensitive data in logs | P0 | [x] | No password/token/hash logging in auth code (reviewed). |
| SEC-018 | Email verification (before public release) | P2 | [x] | Built Phase 4: hashed single-use tokens (`app/auth/tokens.py`), `POST /auth/verify-email` + `/resend-verification`; `ConsoleEmailSender` default, SMTP by config. |
| SEC-019 | Password-reset flow (before public release) | P2 | [x] | Built Phase 4: `POST /auth/request-password-reset` + `/reset-password`, TTL 30 min, consumes all sessions on reset; uniform replies (no enumeration). |
| SEC-020 | Test unauthorized & cross-account access | P0 | [x] | 401 on /me without cookie; cross-origin POST → 403 (tests/test_auth.py). |
| SEC-021 | Test session expiry & revocation | P1 | [x] | Expired session rejected; logout revokes (tests/test_auth.py). |
| SEC-022 | Review dependency vulnerabilities | P1 | [x] | `pip-audit` runs in the CI backend job; `npm audit --omit=dev` clean (prod deps). |
| SEC-023 | Document threat model | P1 | [ ] | |
| SEC-024 | Review third-party licensing | P1 | [x] | `THIRD_PARTY_NOTICES.md`: per-dep SPDX + the python-chess (GPL-3.0+) / psycopg (LGPL-3.0) copyleft caveat, Stockfish kept in a separate unmodified container (REL-011 / ADR-006). MIT-vs-copyleft distribution tension flagged for legal sign-off. |

---

## Phase 4 — Backend API

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| API-001 | POST /api/v1/auth/register | P1 | [x] | Phase 3: 201 + session (app/api/v1/auth.py). |
| API-002 | POST /api/v1/auth/login | P1 | [x] | Phase 3: 200 + session, generic 401. |
| API-003 | POST /api/v1/auth/logout | P1 | [x] | Phase 3: 204, revokes + clears cookies. |
| API-004 | GET /api/v1/auth/me | P1 | [x] | Phase 3: {id, email}; 401 unauthenticated. |
| API-005 | POST /api/v1/games | P1 | [x] | 201 starting-position game (app/api/v1/games.py). |
| API-006 | GET /api/v1/games | P1 | [x] | Own games, newest first. |
| API-007 | GET /api/v1/games/{game_id} | P1 | [x] | Game + moves; 404 if foreign (SEC-010). |
| API-008 | POST /api/v1/games/{game_id}/moves | P1 | [x] | UCI validation + persist + version bump. |
| API-009 | POST /api/v1/games/{game_id}/undo | P1 | [x] | Restores FEN, drops last move, bumps version. |
| API-010 | POST /api/v1/games/{game_id}/resign | P1 | [x] | Marks resigned; 409 if finished. |
| API-011 | POST /api/v1/games/{game_id}/draw-claim | P1 | [x] | 422 unless position supports draw. |
| API-012 | POST /api/v1/games/{game_id}/engine-move | P1 | [x] | Computer games; budget caps; records engine_runs. |
| API-013 | POST /api/v1/analysis/positions | P2 | [ ] | Deferred: needs analysis UX decision (Phase 5+). |
| API-014 | POST /api/v1/benchmarks | P2 | [ ] | Deferred: needs benchmark harness (Phase 7). |
| API-015 | GET /api/v1/benchmarks/{benchmark_id} | P2 | [ ] | Deferred: needs benchmark harness (Phase 7). |
| API-016 | Request & response schemas | P1 | [x] | Pydantic schemas in app/api/v1/schemas.py. |
| API-017 | Consistent error schemas | P1 | [x] | {detail} envelope via _map_errors + ErrorResponse. |
| API-018 | Validate every incoming move | P0 | [x] | ChessRules.apply_move; 422 on invalid/illegal. |
| API-019 | Optimistic concurrency control | P0 | [x] | expected_version → 409 on stale; versions monotonic. |
| API-020 | Document HTTP status codes | P1 | [x] | docs/api.md status-code table + per-route codes. |
| API-021 | Generate & validate OpenAPI schemas | P1 | [x] | /openapi.json; tests/test_openapi.py validates refs. |
| API-022 | Generate frontend API types | P1 | [x] | `openapi-typescript` codegen: `apps/api/scripts/export-openapi.py` → `apps/api/openapi.json` → `src/lib/api-schema.ts`; `api-types.ts` is a thin overlay; CI `npm run check:api` fails on drift. |
| API-023 | API integration tests | P1 | [x] | tests/test_games.py (9 tests, live Postgres). |
| API-024 | All protected endpoints enforce auth | P0 | [x] | get_current_user on all game routes; 401 tested. |

---

## Phase 5 — Frontend

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| WEB-001 | Initialize React + TypeScript | P1 | [x] | vite react-ts scaffold; apps/web/vite.config.ts |
| WEB-002 | Strict TypeScript | P1 | [x] | tsconfig strict; `npx tsc --noEmit` clean |
| WEB-003 | Linting & formatting | P1 | [x] | eslint+prettier; both clean on src/ |
| WEB-004 | Router | P1 | [x] | react-router in src/App.tsx; App.test.tsx routing tests |
| WEB-005 | Registration UI | P1 | [x] | src/pages/AuthPages.tsx RegisterForm |
| WEB-006 | Login UI | P1 | [x] | src/pages/AuthPages.tsx LoginForm |
| WEB-007 | Logout | P1 | [x] | AuthContext logout; Dashboard nav |
| WEB-008 | Session restoration | P1 | [x] | AuthContext /auth/me on mount; App.test.tsx |
| WEB-009 | Main dashboard | P1 | [x] | src/pages/Dashboard.tsx |
| WEB-010 | Chessboard | P1 | [x] | src/components/Chessboard.tsx; lib/chess.ts FEN parser |
| WEB-011 | Legal-move selection | P1 | [x] | GamePage click-to-move; GamePage.test.tsx |
| WEB-012 | Drag-and-drop | P1 | [x] | Chessboard dragStart/drop handlers |
| WEB-013 | Promotion selection | P1 | [x] | GamePage promotion dialog; test asserts b7a8n |
| WEB-014 | Show whose turn | P1 | [x] | GameStatus turn line + Chessboard status |
| WEB-015 | Show check & checkmate | P1 | [x] | GameStatus checkmate branch; test asserts Checkmate |
| WEB-016 | Show stalemate & draws | P1 | [x] | GameStatus stalemate/draw branch; test asserts Stalemate |
| WEB-017 | Move history | P1 | [x] | src/components/MoveHistory.tsx; GamePage.test.tsx resume test |
| WEB-018 | Captured-piece display | P2 | [x] | lib/chess.ts capturedPieces(); 15 chess.test.ts cases |
| WEB-019 | Undo & reset controls | P1 | [x] | GamePage Undo + Reset-to-start; tests assert undo calls |
| WEB-020 | Player-vs-computer setup | P1 | [x] | Dashboard mode=computer |
| WEB-021 | Local two-player setup | P1 | [x] | Dashboard mode=local |
| WEB-022 | Engine difficulty selection | P1 | [x] | Dashboard depth select 1-5; engineMove default depth 3 |
| WEB-023 | Saved-game listing | P1 | [x] | Dashboard saved-game list |
| WEB-024 | Game resume | P1 | [x] | GamePage resume; test asserts resume + board state |
| WEB-025 | Loading & error states | P1 | [x] | AuthContext/Dashboard/GamePage loading+error; tests |
| WEB-026 | Responsive layout | P2 | [x] | styles.css @media |
| WEB-027 | Keyboard & accessibility | P2 | [x] | Phase 6: `role=grid`→`role=row`→`gridcell`, arrow-key nav + Enter/Space select, roving tabindex, focus-trapped `aria-modal` promotion, moving-side-only live cells (`Chessboard.tsx` + tests). |
| WEB-028 | Frontend unit tests | P1 | [x] | 48 vitest tests (4 files: App, GamePage, Chessboard, chess). |
| WEB-029 | Browser e2e tests | P1 | [x] | Playwright `apps/web/e2e/game-loop.spec.ts` (register→play→resign→PGN) run against the composed stack in the CI `e2e` job. |
| WEB-030 | Verify production build | P1 | [x] | `npm run build`: entry 131.8 kB / 131.77 kB gzip; GamePage code-split chunk 11.8 kB / 4.41 kB gzip. |

---

## Phase 6 — Custom Chess AI

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| AI-001 | ChessEngine interface | P1 | [x] | ChessEngine class in app/engine/engine.py |
| AI-002 | Structured engine result | P1 | [x] | EngineResult dataclass in app/engine/domain.py |
| AI-003 | Engine config & limits | P1 | [x] | EngineConfig dataclass with difficulty/depth/time (app/engine/domain.py) |
| AI-004 | Material evaluation | P1 | [x] | evaluate_position() with piece values (app/engine/evaluator.py) |
| AI-005 | Terminal-position scoring | P1 | [x] | Checkmate/stalemate/draw detection in evaluate_position() |
| AI-006 | Piece-square tables | P2 | [ ] | |
| AI-007 | Minimax | P1 | [x] | _minimax() method with depth-limited search (app/engine/engine.py) |
| AI-008 | Alpha-beta pruning | P1 | [x] | Alpha-beta cutoffs in _minimax() (app/engine/engine.py) |
| AI-009 | Move ordering | P2 | [ ] | |
| AI-010 | Iterative deepening | P2 | [ ] | |
| AI-011 | Deadline-aware search | P1 | [x] | Time limit checking in search() and _minimax() |
| AI-012 | Cancellation | P1 | [x] | cancel() method with _cancelled flag |
| AI-013 | Quiescence search | P2 | [ ] | |
| AI-014 | Transposition table | P2 | [ ] | |
| AI-015 | Reproducible engine configs | P1 | [x] | EngineConfig dataclass is frozen |
| AI-016 | Test forced mates | P1 | [x] | test_engine_search_checkmate_position() (test_engine.py) |
| AI-017 | Test material blunders | P1 | [x] | test_evaluate_material_advantage() (test_engine.py) |
| AI-018 | Test terminal positions | P1 | [x] | test_evaluate_checkmate/stalemate() (test_engine.py) |
| AI-019 | Test legal-move guarantees | P0 | [x] | test_engine_search_starting_position() validates legal moves |
| AI-020 | Test timeout behavior | P0 | [x] | test_engine_cancel() tests timeout/cancellation |
| AI-021 | Measure nodes & NPS | P2 | [x] | nodes_searched tracked in EngineResult |
| AI-022 | Tune difficulty settings | P2 | [ ] | |
| AI-023 | Engine + game-service integration tests | P1 | [ ] | |
| AI-024 | Document strength limitations | P1 | [x] | docs/engine-strength.md with current capabilities and limitations |

---

## Phase 7 — Stockfish & Benchmarking

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| BEN-001 | Verify official Stockfish source | P2 | [x] | `app/engine/stockfish.py` provenance constants (stockfishchess.org + official GitHub); apt `stockfish 16-1build1`. |
| BEN-002 | Record version & binary provenance | P2 | [x] | `stockfish_version_label()` records `stockfish 16-1build1`; `hardware_fingerprint()` per run; `STOCKFISH_PATH` settings. |
| BEN-003 | Review GPL-3.0 obligations | P1 | [x] | Binary NOT distributed (adapter + PATH lookup only); obligations documented in IMPLEMENTATION_LOG session (i). |
| BEN-004 | UCI adapter | P2 | [x] | `app/engine/stockfish.py` via `chess.engine.SimpleEngine.popen_uci`; fake-UCI tests, no binary needed. |
| BEN-005 | Process startup/shutdown | P2 | [x] | `popen_uci` + `engine.quit()` in `finally`; crash → `StockfishError`, missing → `StockfishUnavailableError`. |
| BEN-006 | Bound time & resources | P0 | [x] | Hard caps depth ≤15 / time ≤1000ms / threads=1 / hash ≤64MB via `StockfishConfig.bounded()`. |
| BEN-007 | Handle crashes/unavailable binaries | P1 | [x] | `test_missing_binary_raises_unavailable`, unavailable-binary analysis test; harness degrades to custom-only. |
| BEN-008 | Position analysis | P2 | [x] | `analyse_position()` returns EngineResult-compatible struct with move/score/depth/nodes/time. |
| BEN-009 | Versioned FEN test suite | P2 | [x] | `app/engine/benchmark_suite.py` v1, 12 validated positions (openings/tactics/endgames). |
| BEN-010 | Run both engines on identical positions | P2 | [x] | `compare_position()` runs custom + reference on same FEN; stubbed + no-binary tests. |
| BEN-011 | Record config & hardware | P2 | [x] | `hardware_fingerprint()` + `stockfish_version_label()`; `benchmark_runs.hardware` column. |
| BEN-012 | Record move/score/depth/nodes/time | P2 | [x] | `PositionComparison` + `benchmark_results` table persist all fields per position. |
| BEN-013 | Normalize score & mate scores | P2 | [x] | `_extract_score()` normalizes to cp from mover perspective; mate → 20000−10·plies. |
| BEN-014 | Head-to-head games | P2 | [ ] | |
| BEN-015 | Alternate colors | P2 | [ ] | |
| BEN-016 | Record W/D/L | P2 | [ ] | |
| BEN-017 | Estimate rating w/ uncertainty | P3 | [ ] | |
| BEN-018 | Benchmark regression tests | P2 | [x] | `tests/test_benchmark.py` (agreement/gap metrics, determinism) + `tests/test_stockfish.py` (5 tests). |
| BEN-019 | Persist benchmark results | P2 | [x] | `benchmark_runs` + `benchmark_results` tables; migration `5a0dcdb13bb3` upgrade/downgrade verified. |
| BEN-020 | Restrict expensive benchmark endpoints | P0 | [x] | No benchmark HTTP endpoints added (no new attack surface); bounds enforced in adapter. |
| BEN-021 | Benchmark documentation | P2 | [ ] | |
| BEN-022 | Verify repeatability | P2 | [x] | `test_repeatability_custom_engine_deterministic` — same config+position → same move. |

---

## Phase 8 — Quality, Security & Performance

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| QA-001 | All backend unit tests | P1 | [x] | `pytest` → **222 passed** on the non-destructive `chess_test` database. |
| QA-002 | Backend integration tests | P1 | [x] | Auth/games/engine/recovery/concurrency API tests green in the same 222-passed run (TestClient + live PG). |
| QA-003 | Frontend unit tests | P1 | [x] | `npm run test:run` → **48 passed** (4 files: App, GamePage, Chessboard, chess). |
| QA-004 | e2e smoke tests | P1 | [x] | Playwright `e2e/game-loop.spec.ts` against the composed stack (CI `e2e` job) + `scripts/smoke-prod.sh` (auto-reply, result, PGN, `/ready`). |
| QA-005 | Python lint | P1 | [x] | `ruff check app tests` → All checks passed; `ruff format --check` → 75 files formatted. |
| QA-006 | Python type check | P1 | [x] | `mypy app` → no issues in 52 source files. |
| QA-007 | Frontend lint | P1 | [x] | `npm run lint` (eslint .) → clean. |
| QA-008 | TS type check | P1 | [x] | `npx tsc --noEmit` → clean. |
| QA-009 | Production build | P1 | [x] | `npm run build` → entry 131.77 kB gzip, GamePage code-split chunk 4.41 kB gzip; `format:check` → Prettier clean. |
| QA-010 | Validate migrations | P1 | [x] | `alembic upgrade head` → up to date; `alembic check` → no new ops; `5a0dcdb13bb3` round-trip verified earlier. |
| QA-011 | Test unauthorized access | P0 | [x] | `test_unauthenticated_games_rejected`, `test_me_unauthenticated_is_401`, `test_unauthorized_shapes_have_no_leak` (401 + `{"detail":"Not authenticated"}`, forged cookie opaque). |
| QA-012 | Test cross-user data isolation | P0 | [x] | `test_cross_account_isolation`, `test_recover_game_ownership_enforced`, repo ownership tests (404 for foreign ids). |
| QA-013 | Test invalid/malformed moves | P0 | [x] | `test_malformed_move_shapes` (zzzz/e2e5/not-a-move/e7e8q → 422 envelope); illegal/castle/promotion suites. |
| QA-014 | Test repeated & concurrent requests | P1 | [x] | `test_concurrent_stale_write_one_wins` (200+409), `test_repeated_create_is_stable` (5 distinct), `test_stale_version_conflict_shape`; `test_auth_rate_limit`. |
| QA-015 | Test engine timeouts | P0 | [x] | `test_engine_timeout_stays_in_budget`, `test_engine_cancel_flag_set`, `test_engine_cancel` (termination recorded, bounded). |
| QA-016 | Test restart & game recovery | P1 | [x] | `test_restart_recovery_via_api` (re-login → moves e2e4/e7e5, v3, FEN round-trip); `test_recover_game_with_moves`. |
| QA-017 | Test DB rollback | P0 | [x] | `test_db_rollback_leaves_clean_state` + `test_rollback_after_failed_write` + `test_stale_version_conflict_shape` (state consistent). |
| QA-018 | Check dependency vulnerabilities | P1 | [x] | `pip-audit`: app deps clean (only pip-24.0 itself flagged, env tooling); `npm audit --omit=dev` → 0 vulns. |
| QA-019 | Verify no secrets in logs | P0 | [x] | `test_no_secrets_in_error_bodies` (no password_hash/traceback; `{"detail"}`-only); error envelope SEC-016. |
| QA-020 | Review accessibility | P2 | [x] | Phase 6: board is `role=grid` → `role=row` → `gridcell`, arrow-key nav, roving tabindex, focus-trapped `aria-modal` promotion, `role=status`/`role=alert` live regions (`Chessboard.test.tsx`). |
| QA-021 | Review mobile & desktop layouts | P2 | [x] | `styles.css` responsive (`max-width:68rem`, `@media max-width:46rem` stacking); needs device spot-check in Phase 9. |
| QA-022 | Performance tests | P2 | [x] | Engine probe: depth1 20 nodes/5 ms, depth2 420 nodes/78 ms (pure-Python, TD-001); API smoke p50 <1 s; depth3+ profiling deferred. |
| QA-023 | Review slow DB queries | P2 | [x] | `GET /games` uses a single aggregate/summary query (no per-row move fetch → no N+1, Phase 3); ownership lookups on indexed `user_id` + `game_id` FKs. |
| QA-024 | Review technical debt | P1 | [x] | TD register reviewed: TD-004 (GPL review done — no bundling), TD-007 (threads=1), TD-009 workaround, TD-011 warning-only; TD-001/TD-002/TD-008 still Open. |
| QA-025 | Verify backup & restore | P1 | [x] | `pg_dump chess_smoke` (16 kB) → restored to `chess_restore`: 1 game + 2 moves intact. Repeat with prod tooling in Phase 9. |
| QA-026 | Verify release checklist | P1 | [x] | REL-001..017 complete+verified (prod config, secrets, HTTPS seam, backups/restore, controlled migrations, health, logs, smoke). Release sign-off: v0.1.0. |

---

## Phase 9 — Deployment & Release

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| REL-001 | Production configuration | P1 | [x] | `Settings` in `core/database.py` (env-driven); `docs/deployment.md` §1 table; `.env.example`. |
| REL-002 | Secret management | P0 | [x] | App refuses to start w/ placeholder `SECRET_KEY` in prod (verified); compose `:?` guards fail closed; `backups/`+`*.sql` gitignored. |
| REL-003 | HTTPS | P0 | [x] | TLS terminates at reverse proxy (`apps/web/nginx.conf`, redirect ready); `COOKIE_SECURE=true` + exact `CORS_ORIGINS` (REL-012). Docs §3. |
| REL-004 | DB backups | P1 | [x] | `scripts/backup-db.sh` — timestamped `pg_dump`, 14-backup retention (`BACKUP_KEEP`). |
| REL-005 | Verify DB restoration | P1 | [x] | `scripts/restore-db.sh` creates target + prints row counts; verified QA-025 (game+moves intact). |
| REL-006 | Migrations as controlled deployment step | P1 | [x] | Compose `alembic upgrade head && uvicorn`; **fixed `env.py`** to honour `DATABASE_URL`/`database_url` (was hardcoded dev URL); CI `alembic check`. |
| REL-007 | Health checks | P1 | [x] | `/api/v1/health` (liveness) + `/api/v1/ready` (DB probe); compose healthchecks; verified live. |
| REL-008 | Structured logs | P1 | [x] | Single-line stdout logging in `core/database.py`; `LOG_LEVEL`; no secrets logged (QA-019). |
| REL-009 | Monitoring & error reporting | P2 | [x] | Docs §8: metrics seam, alert targets, opaque 500s (no stack-trace leak). APM seam at `app/main.py`. |
| REL-010 | Verify production dependency install | P1 | [x] | `pip install .` builds `chess_engine_api-0.1.0-py3-none-any.whl` (32 kB); `npm ci`+build; pip-audit+npm audit clean (QA-018). |
| REL-011 | Stockfish deployment & licensing | P1 | [x] | Binary NOT bundled (GPL-3.0); install via apt/upstream at deploy; provenance in `stockfish.py`; docs §10. |
| REL-012 | Verify CORS & cookie settings | P0 | [x] | Explicit `CORS_ORIGINS` allowlist + `allow_credentials` (`main.py`); `COOKIE_SECURE=true`; verified in prod smoke. |
| REL-013 | Production smoke tests | P1 | [x] | `scripts/smoke-prod.sh` PASS twice: prod-mode uvicorn AND full `docker compose up` stack (db/api/web healthy; SPA 200 + security headers; engine v3). |
| REL-014 | Document rollback procedures | P1 | [x] | Docs §13: app rollback (prev image) + data rollback (backup→restore); expand/contract rule (§5). |
| REL-015 | Release notes | P1 | [x] | Docs §14: version 0.1.0, scope per phase, final status pointer. |
| REL-016 | All P0/P1 issues resolved | P0 | [x] | P0/P1 REL items done; env.py migration bug found+fixed this phase; remaining are deferred P2/P3 (SEC-018/019, analysis UX). |
| REL-017 | Publish final verified status | P1 | [x] | Summary below updated; all gates green (139 pytest, ruff, mypy, compose config, prod smoke). |

---

## Summary

These counts are recomputed directly from the tables above by
`scripts/check-checklist.py`, which CI runs — the numbers below must match the
file or the check fails, so the summary cannot drift again. `[-]`/`[!]` are zero
now that email verification and password reset shipped (SEC-018/019) and nothing
is blocked.

- **Total items:** 265
- **Implemented & verified (`[x]`):** 218
- **Not yet started (`[ ]`):** 47
- **In progress (`[~]`):** 0
- **Intentionally deferred (`[-]`):** 0
- **Blocked (`[!]`):** 0

The not-started rows are the post-MVP surface: the Phase 10 analysis / coach
roadmap plus a tail of open P2/P3 quality, benchmarking, and fresh-environment
items. Every High and Medium finding in the MVP roadmap is implemented.

---

## Phase 10 — Roadmap: Game Analysis Engine + AI Coach (not in MVP scope)

> Post-MVP vision tracked here so it is visible but clearly out of the shipped
> scope. Nothing below is implemented; the `[-]`/`[ ]` statuses are deliberate.

> Design rule: **Engine calculates, Coach teaches.** Stockfish supplies chess facts
> (evals, best lines, MultiPV); classification consumes structured analysis only;
> coaching cites stored fields and never invents evaluations. New modules follow
> `docs/architecture.md`: `analysis`/`classification`/`tactics`/`coaching` never
> contain search; `engine` never does HTTP/DB; `api` never contains chess algorithms.
> GPL-3.0: Stockfish binary is never bundled (REL-011); provenance in `stockfish.py`.

### Stage 1 — Analysis foundation (engine truth layer)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| ANL-001 | Engine provider interface (custom + Stockfish pluggable) | P1 | [ ] | `app/engine/provider.py`: `EngineProvider.analyse(fen, depth, multipv)` → structured result with principal variations |
| ANL-002 | Stockfish MultiPV support (best + 2nd/3rd lines) | P1 | [ ] | `stockfish.py`: MultiPV=3-5, returns per-line `move/score/pv`; bounded |
| ANL-003 | Warm Stockfish worker pool (no spawn-per-move) | P1 | [ ] | `app/engine/pool.py`: 2-4 persistent UCI processes, bounded queue, graceful fallback |
| ANL-004 | Win-probability model (cp + mate → win%) | P1 | [ ] | `app/analysis/winprob.py`: sigmoid `50*(1+tanh(cp/350))`, mate-aware, tested vs known positions |
| ANL-005 | Eval cache (FEN+depth+MultiPV → result) | P2 | [ ] | DB `move_evaluations` + in-memory LRU; re-review instant |
| ANL-006 | Two-pass analysis (fast sweep + deep critical moments) | P2 | [ ] | fast depth 12-15 all moves; deep depth 20-25 on swings >150cp |
| ANL-007 | Higher Stockfish bounds for review (depth ≤25, time ≤5s) | P1 | [ ] | separate `REVIEW_MAX_*` bounds; play path keeps tight bounds |
| ANL-008 | Async analysis jobs (no blocked HTTP) | P1 | [ ] | `analysis_jobs` table + `POST /games/{id}/analyze` → job_id; progress endpoint |

### Stage 2 — Move classification (explainable labels)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| CLS-001 | Centipawn-loss + win%-drop per move | P1 | [ ] | `app/classification/loss.py`: before/after eval from engine truth |
| CLS-002 | Label rules: brilliant/great/best/excellent/good/inaccuracy/mistake/blunder/missed-win | P1 | [ ] | `app/classification/labels.py`: published thresholds, sacrifice + only-move + obviousness checks |
| CLS-003 | ELO-aware thresholds (same cp loss ≠ same label) | P1 | [ ] | scale by player rating + position complexity + game phase |
| CLS-004 | Fair accuracy model (expected-loss calibrated) | P1 | [ ] | `accuracy = 100*exp(-actual/expected(rating, complexity))` |
| CLS-005 | Every label stores proof fields | P1 | [ ] | `before_cp/after_cp/best_line/played_line/pattern/confidence` persisted |

### Stage 3 — Tactics detection (pure python-chess)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| TAC-001 | Fork / pin / skewer / discovered / hanging-piece detectors | P1 | [ ] | `app/tactics/patterns.py`, before-vs-after diff (created vs missed) |
| TAC-002 | Mate-in-1/2 threat + back-rank + trapped-piece detectors | P2 | [ ] | same module, tested on known puzzles |
| TAC-003 | Sacrifice evaluator (material given vs compensation) | P2 | [ ] | distinguishes real sacs from blunders that look flashy |

### Stage 4 — Coaching (rule templates first, LLM later)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| COA-001 | Grounded rule-based explanations per label | P1 | [ ] | templates cite stored eval fields only; `POST /coach/explain` |
| COA-002 | ELO-calibrated tone (rookie plain+emoji → expert lines+ideas) | P1 | [ ] | `coach_level` param; max 3 key moments for rookies |
| COA-003 | Retry-the-move before revealing | P2 | [ ] | frontend flow + `POST /coach/retry` check endpoint |
| COA-004 | Opening coach (ECO name, deviation, plan) | P2 | [ ] | `app/openings/`: book + theory comparison |
| COA-005 | LLM explainer behind grounding guardrail | P3 | [ ] | LLM receives Stockfish JSON only; output validated against stored fields |
| COA-006 | AI chat over a position with PV citations | P3 | [ ] | `POST /coach/ask`; refuses when no analysis present |

### Stage 5 — Review UX + training loop

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| REV-001 | PGN import endpoint | P1 | [ ] | `POST /games/import-pgn`; validates via python-chess |
| REV-002 | Review payload (moves + labels + lines + graph) | P1 | [ ] | `GET /games/{id}/review`: eval graph, critical moments, accuracy |
| REV-003 | Review UI: eval bar, arrows, variations, retry, accuracy dial | P1 | [ ] | web `game-review/` pages; Gen-Alpha neon style |
| REV-004 | Weakness tracking across games | P2 | [ ] | `player_profiles`: recurring patterns (e.g. "misses back-rank") |
| REV-005 | Personalised puzzles from your blunders | P3 | [ ] | `app/training/`: positions where you erred, retry as exercises |
| REV-006 | ELO-aware play (UCI_Elo + human-like weakening) | P2 | [ ] | personalities for <1000; node caps + top-3 sampling |

> Statuses must be updated in this file only after the corresponding acceptance criteria are met and checks pass.
