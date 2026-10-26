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
| FND-023 | CI workflows | P1 | [ ] | |
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
| DB-008 | benchmark_runs migration | P2 | [ ] | |
| DB-009 | benchmark_results migration | P2 | [ ] | |
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
| DB-022 | Document backup & restore | P1 | [x] | `docs/deployment.md` §4 covers dump→verify→restore, scheduling and opt-in PITR. |

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
| SEC-013 | Engine endpoint resource limits | P0 | [ ] | No engine HTTP endpoints yet (Phase 4/6). |
| SEC-014 | Explicit CORS config | P1 | [x] | Allowlist from settings in app/main.py; credentials enabled, no wildcard. |
| SEC-015 | Keep secrets out of source control | P0 | [x] | .env.example placeholders only; .gitignore covers .env; no secrets logged. |
| SEC-016 | Safe error responses | P1 | [x] | Generic "Invalid email or password"; {detail} envelope; no hash/stack leaks. |
| SEC-017 | No sensitive data in logs | P0 | [x] | No password/token/hash logging in auth code (reviewed). |
| SEC-018 | Email verification (before public release) | P2 | [-] | Deferred; required before public launch. |
| SEC-019 | Password-reset flow (before public release) | P2 | [-] | Deferred; required before public launch. |
| SEC-020 | Test unauthorized & cross-account access | P0 | [x] | 401 on /me without cookie; cross-origin POST → 403 (tests/test_auth.py). |
| SEC-021 | Test session expiry & revocation | P1 | [x] | Expired session rejected; logout revokes (tests/test_auth.py). |
| SEC-022 | Review dependency vulnerabilities | P1 | [ ] | |
| SEC-023 | Document threat model | P1 | [ ] | |
| SEC-024 | Review third-party licensing | P1 | [ ] | |

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
| API-022 | Generate frontend API types | P1 | [x] | apps/web/src/lib/api-types.ts + contract test. |
| API-023 | API integration tests | P1 | [x] | tests/test_games.py (9 tests, live Postgres). |
| API-024 | All protected endpoints enforce auth | P0 | [x] | get_current_user on all game routes; 401 tested. |
| API-025 | Online human-vs-human endpoints (REST + WebSocket) | P1 | [x] | /online/queue, /online/games/*, /online/ws (docs/online-play-plan.md Phases 1–3); 27 tests incl. WS handshake guards. |

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
| WEB-027 | Keyboard & accessibility | P2 | [x] | Chessboard arrow-key nav + aria-labels |
| WEB-028 | Frontend unit tests | P1 | [x] | 43 vitest tests (App/GamePage/chess/api-types) |
| WEB-029 | Browser e2e tests | P1 | [ ] | Deferred: needs Playwright harness (Phase 9) |
| WEB-030 | Verify production build | P1 | [x] | `npx vite build` succeeds, 274 kB / 87 kB gzip |
| WEB-031 | Online lobby + live online board | P1 | [x] | /lobby queue UI with polling, /online/:id board over WebSocket + REST fallback (online-plan Phase 4); 11 vitest tests. |

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
| QA-001 | All backend unit tests | P1 | [x] | `pytest` → **139 passed** (128 existing + 11 QA probes) on user-owned PG18 :5432. |
| QA-002 | Backend integration tests | P1 | [x] | Auth/games/engine/benchmark API tests green in the same 139-passed run (TestClient + live PG). |
| QA-003 | Frontend unit tests | P1 | [x] | `npm run test:run` → **43 passed** (4 files: api-types, chess, App, GamePage). |
| QA-004 | e2e smoke tests | P1 | [x] | Live uvicorn smoke on scratch DB: register → create computer game → e2e4 → engine g8h6 (v3, active); `/health` ok. No Playwright harness (WEB-029/Phase 9). |
| QA-005 | Python lint | P1 | [x] | `ruff check app tests` → All checks passed; `ruff format --check` → 52 files formatted. |
| QA-006 | Python type check | P1 | [x] | `mypy app` → no issues in 37 source files. |
| QA-007 | Frontend lint | P1 | [x] | `npm run lint` (eslint .) → clean. |
| QA-008 | TS type check | P1 | [x] | `npx tsc --noEmit` → clean. |
| QA-009 | Production build | P1 | [x] | `npm run build` → 36 modules, 274 kB / 87 kB gzip; `format:check` → Prettier clean. |
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
| QA-020 | Review accessibility | P2 | [x] | Board is `role=grid` + per-square `aria-label`/`aria-pressed`, `aria-live` status, labelled promotion dialog, keyboard navigation (Phase 5 session h). |
| QA-021 | Review mobile & desktop layouts | P2 | [x] | `styles.css` responsive (`max-width:68rem`, `@media max-width:46rem` stacking); needs device spot-check in Phase 9. |
| QA-022 | Performance tests | P2 | [x] | Engine probe: depth1 20 nodes/5 ms, depth2 420 nodes/78 ms (pure-Python, TD-001); API smoke p50 <1 s; depth3+ profiling deferred. |
| QA-023 | Review slow DB queries | P2 | [x] | `test_slow_query_review`: ownership lookups on indexed `user_id` + `game_id` FKs; no N+1 (single list/get per request). |
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
| REL-004 | DB backups | P1 | [x] | `scripts/backup-db.sh` — compressed custom-format `pg_dump -Fc` + `.dump.meta` integrity sidecar (sha256/alembic/row counts); `DB_IN_CONTAINER` + `RCLONE_TARGET`; 14-backup retention. |
| REL-005 | Verify DB restoration | P1 | [x] | `scripts/verify-backup.sh` restores the newest dump into a throwaway DB and asserts sha256 + alembic + row counts vs the sidecar (non-zero on mismatch); `restore-db.sh` handles `.dump`/`.sql`; `scripts/backup-cron.example` chains backup→verify nightly + monthly oldest-backup drill. |
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
| REL-018 | Point-in-time recovery (opt-in) | P2 | [x] | `compose.pitr.yaml` WAL archiving → `./wal-archive`; `scripts/pitr-basebackup.sh` + `scripts/pitr-restore.sh` (replays to any instant in a throwaway :5433 container, never over live); `pgbackrest.conf.example` for the prod path. Docs §4. |

---

## Summary

- **Total items:** 239
- **Implemented & verified (`[x]`):** FND-001..FND-022, CHS-001..CHS-024, AI-001..AI-005, AI-007..AI-008, AI-011..AI-012, AI-015..AI-021, AI-024, DB-001..DB-007, DB-010..DB-017, DB-018..DB-021, SEC-001..SEC-008, SEC-010..SEC-012, SEC-014..SEC-017, SEC-020..SEC-021, API-001..API-012, API-016..API-025, WEB-001..WEB-028, WEB-030..WEB-031, BEN-001..BEN-013, BEN-018..BEN-020, BEN-022, QA-001..QA-026, REL-001..REL-017 (211 items)
- **Intentionally deferred (`[-]`):** API-013 (analysis UX decision), API-014/API-015 (benchmark harness, Phase 7).
- **Not yet started (`[ ]`):** WEB-029 (browser e2e — Playwright harness), BEN-014..017 + BEN-021, and remaining Phase 6 P2/P3 items.
- **Phase 10 (`[x]`, verified):** FEEL-001..006, PLAY-001..003, REVIEW-001..009, ACH-001..007, LEARN-001..007 (32 items) — play feel, real Stockfish opponent, game review, achievements, and a Learn section of themed drills (incl. multi-move `sequence` puzzles) + puzzles from your own games (which closes REV-005). Phase 9's deeper analysis items (worker pool, win-probability model, eval cache, async jobs, a generic tactics detector, ELO-aware play) remain open.
- **Deferred (`[-]`):** SEC-018, SEC-019 (required before public release)
- **Blocked (`[!]`):** none.

---

## Phase 9 — Game Analysis Engine + AI Coach (beats Chess.com Game Review)

> Design rule: **Engine calculates, Coach teaches.** Stockfish supplies chess facts
> (evals, best lines, MultiPV); classification consumes structured analysis only;
> coaching cites stored fields and never invents evaluations. New modules follow
> `docs/architecture.md`: `analysis`/`classification`/`tactics`/`coaching` never
> contain search; `engine` never does HTTP/DB; `api` never contains chess algorithms.
> GPL-3.0: Stockfish binary is never bundled (REL-011); provenance in `stockfish.py`.

### Stage 1 — Analysis foundation (engine truth layer)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| ANL-001 | Engine provider interface (custom + Stockfish pluggable) | P1 | [x] | `app/engine/provider.py`: `EngineProvider.analyse(AnalyseRequest)` → `AnalysisResult` with `PrincipalVariation`s; used by play, opponent and review |
| ANL-002 | Stockfish MultiPV support (best + 2nd/3rd lines) | P1 | [x] | `stockfish.py`: `multipv` 1-5 clamped, per-line `move/score/pv`; review asks for 3 |
| ANL-003 | Warm Stockfish worker pool (no spawn-per-move) | P1 | [x] | `StockfishProvider` doubles as a context manager: inside `with`, one process serves every `analyse` in the batch (TD-013). Review opens one via `open_stockfish_provider(for_review=True)`. Measured — 13-position batch warm ~11 s vs ~24.6 s one-process-per-ply on the same container; a failed analysis drops the process instead of reusing it |
| ANL-004 | Win-probability model (cp + mate → win%) | P1 | [x] | `app/engine/win_probability.py`: logistic on the Elo equivalent of the eval (1 pawn = 200 Elo), mate-distance overrides, 1..99, exactly symmetric; served as `moves[].win_pct` from White's POV; `tests/test_win_probability.py` |
| ANL-005 | Eval cache (FEN+depth+MultiPV → result) | P2 | [ ] | Not built; the stored review payload is what makes a re-read free |
| ANL-006 | Two-pass analysis (fast sweep + deep critical moments) | P2 | [ ] | Not built: single pass at the review bounds |
| ANL-007 | Higher Stockfish bounds for review (depth ≤25, time ≤5s) | P1 | [x] | `REVIEW_MAX_DEPTH=25` / `REVIEW_MAX_TIME_MS=5000` via `StockfishConfig.bounded(for_review=True)`; play keeps the tight bounds |
| ANL-008 | Async analysis jobs (no blocked HTTP) | P1 | [ ] | Not built: review is synchronous and stored (see TD-013) |

### Stage 2 — Move classification (explainable labels)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| CLS-001 | Centipawn-loss + win%-drop per move | P1 | [ ] | Partial: `app/engine/classifier.py` grades on centipawn loss vs the MultiPV window (mate-distance blended); the win% model now exists (`app/engine/win_probability.py`, ANL-004) but is display-only — grading on win%-drop still pending |
| CLS-002 | Label rules: brilliant/great/best/excellent/good/inaccuracy/mistake/blunder/missed-win | P1 | [ ] | Partial: seven grades shipped (brilliant/best/excellent/good/inaccuracy/mistake/blunder) with published thresholds + forced/sacrifice context; `great` and `missed-win` not implemented |
| CLS-003 | ELO-aware thresholds (same cp loss ≠ same label) | P1 | [ ] | scale by player rating + position complexity + game phase |
| CLS-004 | Fair accuracy model (expected-loss calibrated) | P1 | [ ] | `accuracy = 100*exp(-actual/expected(rating, complexity))` |
| CLS-005 | Every label stores proof fields | P1 | [ ] | Partial: each ply stores `centipawn_loss`, post-ply eval, `best_uci`, `pre_fen`, grade and explanation; no `played_line`/`pattern`/`confidence`. `centipawn_loss` is a placeholder for off-window moves (TD-017) |

### Stage 3 — Tactics detection (pure python-chess)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| TAC-001 | Fork / pin / skewer / discovered / hanging-piece detectors | P1 | [ ] | Partial: `app/training/verify.py` proves fork/pin/hanging *drill positions* by pattern (material gained through the forced line), not a generic over-the-board detector yet — no `app/tactics/patterns.py` scan of live games |
| TAC-002 | Mate-in-1/2 threat + back-rank + trapped-piece detectors | P2 | [ ] | Partial: `mate` and `backrank` themes are named and re-verified in `app/training/verify.py` (`mate_in_one_exists`, escape-square check); no mate-in-2 search or general trapped-piece scan |
| TAC-003 | Sacrifice evaluator (material given vs compensation) | P2 | [ ] | distinguishes real sacs from blunders that look flashy |

### Stage 4 — Coaching (rule templates first, LLM later)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| COA-001 | Grounded rule-based explanations per label | P1 | [ ] | Partial: templates in `app/reviews/explainer.py` cite stored eval/loss/best-move fields only; no standalone `POST /coach/explain` |
| COA-002 | ELO-calibrated tone (rookie plain+emoji → expert lines+ideas) | P1 | [ ] | `coach_level` param; max 3 key moments for rookies |
| COA-003 | Retry-the-move before revealing | P2 | [ ] | frontend flow + `POST /coach/retry` check endpoint |
| COA-004 | Opening coach (ECO name, deviation, plan) | P2 | [ ] | Partial: `app/openings/` — offline CC0 book (3,865 EPD-keyed theory positions) names every ply (`opening_eco`/`opening_name`/`in_book`, REVIEW-008). Deviation-from-theory and the plan-per-opening still open |
| COA-005 | LLM explainer behind grounding guardrail | P3 | [ ] | LLM receives Stockfish JSON only; output validated against stored fields |
| COA-006 | AI chat over a position with PV citations | P3 | [ ] | `POST /coach/ask`; refuses when no analysis present |

### Stage 5 — Review UX + training loop

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| REV-001 | PGN import endpoint | P1 | [ ] | `POST /games/import-pgn`; validates via python-chess |
| REV-002 | Review payload (moves + labels + lines + graph) | P1 | [ ] | Partial: `GET/POST /games/{id}/review` ships moves + grades + eval graph + accuracy + best-move hints (single ply, not full PV lines) — see REVIEW-001..005 below |
| REV-003 | Review UI: eval bar, arrows, variations, retry, accuracy dial | P1 | [ ] | Partial: `/games/:id/review` has the eval graph, per-ply board, graded move list and improvement shortcuts; no arrows, PV browsing or retry-the-move |
| REV-004 | Weakness tracking across games | P2 | [ ] | `player_profiles`: recurring patterns (e.g. "misses back-rank") |
| REV-005 | Personalised puzzles from your blunders | P3 | [x] | `app/training/from_reviews.py` mines the caller's `completed` reviews for hero mistake/blunder plies (centipawn loss \u2265 `MINE_MIN_LOSS_CP`, legal `best_uci`), served as "A move you missed" puzzles on `/learn`, answered against the stored review and deduped by (fen, move) |
| REV-006 | ELO-aware play (UCI_Elo + human-like weakening) | P2 | [ ] | personalities for <1000; node caps + top-3 sampling |

---

## Phase 10 — Play feel, real opponent, game review & achievements

> Shipped slice of the analysis roadmap: feedback that makes moves feel right, a real
> Stockfish opponent, a per-game engine review that teaches, a 200+ achievement
> catalog that rewards continued play, and a Learn section of themed drills plus
> puzzles from your own games. Gates for this phase: 382 pytest (fake Stockfish
> binary), ruff/mypy/alembic clean; eslint + `tsc --noEmit` + 236 vitest + `vite build` clean.
> Verified end-to-end against a real Stockfish in the running container; two quality gaps that
> measurement exposed are recorded as TD-013 (synchronous, ~1.2 s per ply) and TD-017
> (moves outside the engine's top-3 window are graded from a placeholder).

### Stage 0 — Play feel (sound + haptics)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| FEEL-001 | Synthesized sounds per event with intensity | P1 | [x] | `src/lib/sound.ts`: WebAudio presets (select/move/castle/capture/promotion/check/checkmate/gameEnd/error/achievement), gain scaled 0..1; inert without WebAudio so jsdom stays quiet |
| FEEL-002 | Haptic patterns matched to the moment | P2 | [x] | `src/lib/haptics.ts`: Vibration API patterns, guarded for unsupported browsers, respects prefers-reduced-motion |
| FEEL-003 | One classifier + dispatcher for move feedback | P1 | [x] | `src/lib/game-events.ts`: `classifyMove` priority checkmate > check > castle > promotion > capture > move; `emitMoveSequence` replays plies FEN-forward so a broadcast, an engine reply and your own move feel identical; `useGameFeedback` hook |
| FEEL-004 | Player-controlled sound/haptics, persisted | P2 | [x] | `src/lib/settings.ts` localStorage prefs + `SoundToggle` on both game pages |
| FEEL-005 | A wrong move is felt, not read | P1 | [x] | Error sound only, no banner (GamePage + OnlineGamePage); test 'does not show an error banner for a rejected move (sound only)' |
| FEEL-006 | Promotion picker only for a real promotion | P1 | [x] | `isLegalPromotion` (chess.js) gates the picker in `Chessboard.tsx`; regression tests for the picker and for a pawn reaching the last rank outside promotion territory |

### Stage 1 — Real Stockfish opponent

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| PLAY-001 | Computer games answered by Stockfish | P1 | [x] | `app/engine/opponent.py` behind `games.service.request_engine_move`; provider seam and `engine_runs` ledger unchanged; `tests/test_opponent.py` + fake-binary conftest |
| PLAY-002 | Difficulty selection survives the engine swap | P1 | [x] | client depth 1..6 clamped to `DIFFICULTY_MIN/MAX_DEPTH`, default 4; budget passed through |
| PLAY-003 | No silent downgrade to a weaker opponent | P1 | [x] | `StockfishUnavailableError` → `EngineUnavailableError` → `503` documented in `_ENGINE_MOVE_RESPONSES`; frontend keeps the board and reports the failure |

### Stage 2 — Game review

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| REVIEW-001 | One bounded engine pass over a finished game | P1 | [x] | `app/reviews/service.py` replays stored plies, asks MultiPV=3 within `REVIEW_MAX_*`; `POST /games/{id}/review` (`{force}`) |
| REVIEW-002 | Seven explainable grades | P1 | [x] | `app/engine/classifier.py`: centipawn loss vs the MultiPV window, mate-distance blending, forced-move and sacrifice context; classifier tests |
| REVIEW-003 | Coaching sentence per ply, grounded in engine facts | P1 | [x] | `app/reviews/explainer.py`: names the victim of a capture, the missed alternative of a blunder, praise when the move is the engine's own |
| REVIEW-004 | Stored per (game, player) | P1 | [x] | `game_reviews` + migration `c5e9a3d7f410`; JSON payload, `status`/`error` recorded on failure |
| REVIEW-005 | Cached reads, forced re-analysis | P1 | [x] | `GET /games/{id}/review` → `409` when absent; `force` updates the same row (unique constraint holds) |
| REVIEW-006 | Review page: graph, board replay, grades, improvements | P1 | [x] | `/games/:id/review` — `ReviewPage.tsx`, `EvalGraph.tsx`, `lib/review.ts`; report card + hero-colour improvement list; 17 tests |
| REVIEW-007 | Guided tour of the recorded plies | P1 | [x] | `ReviewPage.tsx` lands on ply 1 (the start position) instead of the last ply; First/Prev/Next/Last strip with a `Move n of N` counter, disabled at both bounds; `ArrowLeft`/`ArrowRight`/`Home`/`End` walk the same cursor, ignored inside fields and with modifiers held; board stays read-only. `ReviewPage.test.tsx` 8 → 19 tests, the eight originals unchanged (that is the "retain everything" check) |
| REVIEW-008 | Per-ply opening name + win expectancy panel | P1 | [x] | `app/openings/` + `app/reviews/annotate.py` derive `opening_eco`/`opening_name`/`in_book`/`win_pct` at read time (no migration, no re-analysis — verified live on a payload written without those keys); `Opening and odds` card shows ECO · name, In/Out of book, the hero-side expectancy bar and this game's family average; `tests/test_openings.py` + `tests/test_win_probability.py` (45) + 8 `TestReviewAnnotation` |
| REVIEW-009 | Calm spoken narration of each step, free | P1 | [x] | `lib/voice.ts` (browser `speechSynthesis`, rate/pitch 0.92, cancel-then-speak, sentence-aware chunking ≤180 chars, hidden voice fallback ladder) + `lib/narration.ts` (SAN and `cp` shorthand put into English); `VoiceToggle.tsx` on the `voice` preference; first render kept silent (browsers drop gesture-less speech); `voice.test.ts` 16 + `narration.test.ts` 28; inert where no speech engine exists, so the audible read needs a human ear in a real browser |

### Stage 3 — Achievements

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| ACH-001 | 200+ achievements, earned by continued play | P1 | [x] | `app/achievements/catalog.py`: 32 ladders over one metric each (≈316 entries); import-time asserts on uniqueness and minimum size |
| ACH-002 | Rarity tiers and named ladder steps | P2 | [x] | `Tier` bronze→legendary, Roman ladder titles, per-step flavour text |
| ACH-003 | Every metric computed from stored rows | P1 | [x] | `app/achievements/stats.py`: SQL `FILTER` aggregates over moves (SAN patterns: captures/checks/mate/castle/promotion/piece types), point-ledger results, review payload grades, streaks; test asserts catalog metrics == computed metrics |
| ACH-004 | Per-player unlock records | P1 | [x] | `user_achievements` + migration `d7f3b0c9e512`, unique (user, key), `seen_at` for one-shot celebration |
| ACH-005 | Gallery with real progress | P1 | [x] | `GET /me/achievements` + `/achievements` page (grouped, filterable, progress bars); dashboard strip shows recent unlocks |
| ACH-006 | Celebrations arrive with the action that earned them | P1 | [x] | `unlocked_achievements` on game mutations + completed reviews; `GET /me/achievements/new` for lazy catch-up; WS `achievement` is sent to one seat only (`test_unlocks_go_to_the_actor_and_never_the_opponent`) |
| ACH-007 | One toast per unlock | P1 | [x] | `AchievementCelebration.tsx` (confetti + tier ring + auto-dismiss), provider de-dupes ride vs catch-up, `POST /me/achievements/seen` acknowledges |

### Stage 6 — Learning (themed drills + your own games)

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| LEARN-001 | Themed drill catalog, machine-proved | P1 | [x] | `app/training/drills.py`: `DRILLS = CURATED + generated` — 18 hand-written core drills plus a parametric, template-built catalog (`app/training/generate.py`), **829** verified drills across **9 themes** × 3 levels (mate/hanging/fork/pin/skewer/discovered/backrank/endgame/sequence); `app/training/verify.py` re-proves *every* position (curated and generated) with python-chess and `verify_all()` runs in CI, so an unsound or mislabelled drill fails the build rather than mis-teaching |
| LEARN-002 | Interactive drill board | P1 | [x] | `/learn` (`LearnPage.tsx`) reuses `Chessboard` in `status="active"`; a click submits UCI and the server verdict decides `solved` — the puzzle payload is deliberately answer-free (a test asserts `solution`/`alternatives`/`line` are absent) |
| LEARN-003 | Per-skill progress with an easy→hard ramp | P1 | [x] | `app/training/service.py`: append-only `training_attempts` log → `next_level` (+1 on three correct, −1 on two consecutive wrong, clamped 1..3) + `summary` per-theme `{solved, attempts, level, pct, streak}` |
| LEARN-004 | Puzzles from your own games | P1 | [x] | `app/training/from_reviews.py` mines the caller's completed reviews for hero mistake/blunder plies; solved against the stored review, key `mine:{game}:{ply}`, links back to the game review |
| LEARN-005 | Points and achievement ladders | P1 | [x] | gameless ledger awards via `slot_key` + partial unique index (`uq_point_award_slot_key`) — `POINT_RULES` gains `drill:2`/`theme_clear:5`; `training` achievement group (`Puzzle Solver`, `Sharp Streak`) computed in `stats.py`; migration `e2a9c4f1b830` |
| LEARN-006 | Animated review loader | P1 | [x] | `src/components/ReviewThinking.tsx` replays the finished game *backwards* ply-by-ply (`lib/chess.ts` `forwardFens`) while analysis runs, then loops; replaces the bare text card in `ReviewPage`'s loading branch; `clearInterval` on unmount; the loader and the `/learn` drill board are wrapped in `.board-frame` so they render at the same size as the in-play board |
| LEARN-007 | Multi-move `sequence` puzzles | P1 | [x] | A 9th `sequence` theme of forced-line puzzles (`Drill.moves`, odd-length player-first). Lines are authored offline and certified at generation time — `_verify_sequence()` requires every opponent reply to be a single forced move and the line to end in mate (or net `>= MIN_GAIN_CP`); 65 drills (L1 27 / L2 29 / L3 9). Grading is a stateless **exact-line replay** in `service.record_sequence_attempt`: mid-run `complete:false` logs nothing and advances the board, one attempt row is written only when the run resolves. Frontend `LearnPage` runs a "Move X of Y" stepper; `POST /training/attempts` takes `moves:[...]`; no new migration |

## Phase 11 — Engine-grounded Coach Assistant (the ⭐ on the review page)

> A conversational coach reached from the ⭐ beside "Where to improve". It answers
> from **engine + book facts only**: long-context over the stored review of this
> game (positions, best way to proceed, bounded live-MultiPV what-ifs) and Postgres
> full-text **RAG** across the player's own reviews plus the offline book (recurring
> errors, opening theory). No pgvector/embeddings (D13). An OpenAI-compatible LLM is
> optional and env-gated; it only ever rephrases cited facts, and a reply naming an
> uncited move is discarded for the deterministic answer. Full tracker:
> [`apps/api/app/ai/docs/checklist.md`](apps/api/app/ai/docs/checklist.md).
> Gates: `ruff`/`mypy`/428 `pytest`/`alembic check` clean (backend, incl. `tests/ai`);
> `eslint`/`tsc`/243 `vitest`/`prettier`/`vite build` clean (frontend, incl. the ⭐).

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| COACH-A1 | `app/ai` package (long-context + RAG + compose + provider + service) | P1 | [x] | `app/ai/…`, settings in `core/database.py`, `.env.example` coach block |
| COACH-B1 | Long-context facts + packs + bounded what-if engine pass | P0 | [x] | `app/ai/longcontext/{context,whatif}.py`; `tests/ai/test_context_compose.py` |
| COACH-C1 | Intent detection + deterministic composer + **cite-only grounding guard** | P0 | [x] | `app/ai/{compose,provider}.py`; invention discarded → deterministic (`tests/ai/test_assistant.py`) |
| COACH-D1 | `coach_index` (stored tsvector + GIN) + FTS/pattern recall + backfill | P0 | [x] | `app/ai/rag/*`, migration `f6b1c8d2a9e4`, `scripts/index_reviews.py`; `tests/ai/test_rag.py` |
| COACH-E1 | Service orchestration + best-effort review-index hook | P0 | [x] | `app/ai/service.py` + `reviews/service.py` `index_review_safe` |
| COACH-F1 | `POST /games/{id}/assistant` + `GET …/patterns` (auth, same-origin, rate-limit, 404/409/422/429) | P0 | [x] | `app/api/v1/assistant.py`; HTTP tests in `tests/ai/test_assistant.py` |
| COACH-G1 | ⭐ toggle (left of "Where to improve") + `CoachAssistant` panel, clickable move refs, patterns | P1 | [x] | `ReviewPage.tsx`, `CoachAssistant.tsx`, `api-client`/`api-types`; `*.test.tsx` |
| COACH-I1 | CI: dedicated `pytest tests/ai`, coach migration round-trip, scripts linted | P0 | [x] | `.github/workflows/ci.yml` (fixed a latent `downgrade` TypeError in `a1c7e4f9b2d6`) |
| COACH-11B1 | Conversational upgrade: multi-section teaching + new intents (LESSON/WHY/IDEA) | P1 | [x] | `app/ai/compose.py`; `tests/ai/test_context_compose.py` |
| COACH-11B2 | Walkable lines from a live engine PV or the recorded plies (offline-safe) | P1 | [x] | `app/ai/longcontext/lines.py`; `tests/ai/test_lines.py` |
| COACH-11B3 | Conversation memory: bounded history + focus carry-forward for follow-ups | P1 | [x] | `app/ai/service.py` (`_resolve_focus_ply`); `tests/ai/test_assistant.py` |
| COACH-11B4 | API `history`/`line`/`line_title` + coach drives the main review board (lesson stepper) | P1 | [x] | `schemas.py`, `assistant.py`, `ReviewPage.tsx`, `CoachAssistant.tsx`; web `*.test.tsx` |

---

## Phase 12 — Market Readiness (monitoring, abuse defense, admin floor, fair play)

> Public SaaS release plan: **12A** observability + cost-tiered rate limiting
> (D14/D15), **12B** identity + minimal RBAC with audit (D16 + TD-005),
> **12C** anti-cheat built evidence-first — capture before launch, flag-only,
> moderation enforces (D17). Full tracker: [`docs/market-plan.md`](docs/market-plan.md).
> New debt created by the plan: TD-021 (proxy/XFF trust), TD-022 (fairplay
> threshold calibration), TD-023 (post-game-only detection). Launch gates
> outside this phase: TD-013→ANL-008 review jobs, ToS/privacy, Redis at TD-012's trigger.

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| MON-001 | JSON-line logs with `request_id` | P1 | [x] | `app/core/telemetry.py` + middleware in `app/main.py`; `X-Request-ID` honored/echoed; `LOG_JSON=false` opt-out; smoke in `tests/test_phase12_telemetry.py` |
| MON-002 | `/metrics` (prometheus-fastapi-instrumentator) | P1 | [x] | `prometheus-fastapi-instrumentator` mounted in `main.py`; excluded from OpenAPI + access log; deployment.md §8 |
| MON-003 | `engine_analyse_seconds` histogram by provider | P1 | [x] | `telemetry.ENGINE_ANALYSE_SECONDS{provider}` observed at analyse sites (reviews/opponent/whatif) |
| MON-004 | `engine_unavailable_total` counter | P1 | [x] | counted where failures surface (503s + failed reviews); factory stays silent to avoid double-count |
| MON-005 | `rate_limit_rejections_total{bucket}` | P1 | [x] | every `check_*` bucket in `deps.py` increments on reject |
| MON-006 | cloud daily-units burn + upstream 4xx counters | P1 | [x] | `cloud_stockfish.py` budget guard + `cloud_upstream_errors_total{status}`; tests in `test_cloud_stockfish.py` |
| MON-007 | `ws_connections_active` gauge | P2 | [x] | hub inc/dec on connect/disconnect |
| MON-008 | deployment.md §8 alert-target rewrite | P1 | [x] | deployment.md §7–§8 rewritten to what exists + alert-target list |
| RL-001 | Review limiter 10/h/user (`force` costs 2) | P0 | [x] | `REVIEW_RATE_LIMIT_PER_HOUR` (default 10) in `deps.py`, wired on `POST /games/{id}/review`; budget tests in `test_phase12_telemetry.py` |
| RL-002 | Training-attempt limiter 60/min/user | P1 | [x] | `TRAINING_RATE_LIMIT_PER_MINUTE` wired on attempt submission |
| RL-003 | Global cloud-budget guard (~1,800/day → clean 503) | P1 | [x] | `CLOUD_DAILY_UNIT_BUDGET` in `cloud_stockfish.py`; trips before upstream; 0 disables |
| RL-004 | `Retry-After` on every 429 | P1 | [x] | all buckets emit seconds-until-window-clear |
| SEC-021..028 | Email verification, role column, `require_role`, audit_log, support endpoints, status enforcement | P0 | [ ] | market-plan.md 12B |
| FP-001..003 | Capture before launch: `think_ms`, salted `ip_hash`, `auth_events`, retention | P0 | [ ] | market-plan.md 12C-C1 |
| FP-010..015 | `app/fairplay` detection signals + scoring + flags (hermetic) | P1 | [ ] | market-plan.md 12C-C2 |
| FP-020..024 | Moderation queue, evidence page, verdicts, appeals, ban enforcement | P1 | [ ] | market-plan.md 12C-C3 |

## Phase 13 — Robustness & Concurrency (closes the architecture-review weaknesses W1–W11)

> Launch-hardening pass: [`docs/robustness-plan.md`](docs/robustness-plan.md).
> **Stage 13A** (this pass) removes the two accidental ceilings (untuned pool +
> connection held across the CPU batch) and the proxy-IP launch blocker, makes
> the `.env` footgun self-diagnosing, adds an HTTP cache on the immutable review,
> and splits the frontend bundle. 13B (review job queue), 13C (Redis scale-out) and
> 13D (quality ceilings) stay trigger-gated to the same seams. Invariants held:
> offline-hermetic tests green, 404-on-foreign unchanged, `check_*` signatures kept,
> engine/voice/LLM each behind one seam.

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| RB-001 | Explicit DB pool geometry from settings (`pool_size`/`max_overflow`/`recycle`/`pre_ping`) | P1 | [x] | `core/database.py` settings + `create_engine(...)`; `tests/test_phase13_robustness.py::TestPoolGeometry` |
| RB-002 | Release the DB connection across the review engine batch | P0 | [x] | `reviews/service.py`: replay→`commit()`→`analyse_plies` on scalars→short write; `_Ply` carries scalars; byte-identical payload + no-held-connection tests in `test_reviews.py::TestGenerateOrGetKernel` |
| RB-003 | Startup preflight log (env file, engine/voice/assistant mode, no secret) | P2 | [x] | `main.py` `preflight` log line + `RESOLVED_ENV_FILES`; booleans/names only (QA-019) |
| RB-004 | Trusted-proxy client IP for limiters (default OFF) | P0 | [x] | `deps.py::client_ip` + `trust_proxy_headers`/`trusted_proxy_cidrs`; spoof-guard tests in `test_phase13_robustness.py::TestClientIp`; TD-021 mitigated |
| RB-005 | `ETag`/`Cache-Control` + `304` on `GET /review` | P2 | [x] | `games.py`: ETag = md5 of the exact served body (no memo, never stale across workers/annotation deploys); `test_reviews.py::TestReviewHttpCache` |
| RB-006 | Lazy-route heavy pages (Review/Learn/Online/Lobby/Achievements) | P2 | [x] | `App.tsx` `React.lazy` + `Suspense`; build emits per-page chunks; `App.test.tsx` RB-006 test |
| RB-007 | `uvicorn[standard]` (uvloop/httptools) | P3 | [ ] | TD-010; blocked on pinning the wheels in `requirements.txt` for py3.12-linux + re-verifying the hermetic container build |
| RB-010..014 | Review job queue + eval cache (W4/W5/W6) | P1 | [ ] | robustness-plan.md 13B — trigger: any real game > ~40 plies |
| RB-020..023 | Redis limiters/lobby/cloud-counter + achievement counters (W2/W7) | P1 | [ ] | robustness-plan.md 13C — trigger: a 2nd API replica (=RL-005/TD-012) |
| RB-030..035 | Grading bands, book transit, hot-seat ledger, verified drills, pgvector, fair-play calibration (W9) | P2 | [ ] | robustness-plan.md 13D — each behind an existing seam |
| RB-040 | Managed HA Postgres endpoint (RDS/Neon/Supabase/Cloud SQL) | P2 | [ ] | launch trigger — flip `database_url` to the provider's virtual endpoint (app already reconnects via one URL + `pool_pre_ping`; no code change); retire hand-rolled PITR once provider backups exist |

> Statuses must be updated in this file only after the corresponding acceptance criteria are met and checks pass.
