# Project Plan & Roadmap

> Version 0.2 — last updated 2026-10-22
> This plan is the operational roadmap. It mirrors `PROJECT_CHECKLIST.md`, which is the authoritative status tracker.

## Objective

Build a browser-based chess application: standard chess, player-vs-computer against **Stockfish**, local two-player, user accounts with recovery, PostgreSQL persistence, saved games/move history, and a responsive React + TypeScript frontend — delivered through verified, incremental loops. A hand-written Python engine remains as the degraded fallback behind the `EngineProvider` seam.

## Guiding principles

1. **Correctness first, AI strength second.** An illegal move or corrupted game is a P0 defect.
2. **Modular monolith.** Separate rules, AI search, services, API, persistence, and UI.
3. **python-chess for rules.** Never write a duplicate rules engine.
4. **Verify before claiming done.** No `[x]` without passing checks.
5. **Incremental loops.** INSPECT → PLAN → IMPLEMENT → TEST → REVIEW → FIX → DOCUMENT → VERIFY → REPEAT.

## Milestones (in dependency order)

| # | Milestone | Exit criterion | Target phases |
|---|-----------|----------------|---------------|
| M0 | Foundation & repository | Both apps start, PostgreSQL reachable, checks execute, setup docs accurate | Phase 0 |
| M1 | Chess rules & local gameplay | Complete legal game playable, saved & restored | Phase 1 (+ API subset) |
| M2 | Accounts & persistence | User logs in and resumes own games; cannot see others' | Phases 2–3 |
| M3 | First custom AI | AI returns legal moves within its search budget | Phase 6 |
| M4 | Stockfish & benchmarks | Repeatable custom-vs-Stockfish comparisons | Phase 7 |
| M5 | Hardening & usability | Main journeys reliable; edge cases, a11y, security, backups | Phase 8 |
| M6 | Deployment & first release | Deployed release passes smoke tests; recoverable data | Phase 9 |

## Sequencing rules

- Address any **P0** defect before adding features.
- Do not start Phase 6 (AI) until Phase 1 (rules) is stable.
- Do not start Phase 7 (Stockfish) until the engine interface (AI-001..AI-003) exists.
- `SEC-018` (email verification) and `SEC-019` (password reset) shipped in the
  account-recovery work (Phase 4), behind a sender abstraction; `ConsoleEmailSender`
  is the default so dev needs no mail config.

## Current roadmap — Product-Complete MVP

The foundational milestones (M0–M6) are complete. The active effort is the
seven-phase **Product-Complete MVP roadmap** (plan file
`Product-complete_MVP_roadmap`), which took the codebase from a correct-but-not-a-
product state to a shipped game loop. Each phase has a hard exit gate; a phase is
not started until the previous gate is green.

| Phase | Theme | Exit gate (all green) |
|---|---|---|
| 0 | Unblock the dev loop | fresh clone → README run → non-destructive `pytest` |
| 1 | Atomic persistence core | unit of work + conditional update; threaded contention test; `alembic check` |
| 2 | Stockfish sidecar + provider seam | tactical suite for all providers; killed sidecar degrades, never 500 |
| 3 | Real game loop | sign-up → play as black on hard → auto-reply → mate recorded → resume → PGN |
| 4 | Auth & security | hashed tokens, proxy-aware limits, CSRF, recovery flow; security tests |
| 5 | Deployment & CI | composed stack, non-root, coverage floor, audits, Playwright e2e |
| 6 | A11y, code splitting, OpenAPI, docs | board keyboard-accessible; generated types + drift check; docs truth pass |

## Environment reality check (2026-10-22)

| Tool | Status | Impact |
|------|--------|--------|
| Python 3.14 (project venv) | ✅ present | Backend & engine OK |
| Node 20+ / npm | ✅ present | Frontend OK |
| Docker | ✅ installed | Full `docker compose up` path works; images/e2e run in CI |
| PostgreSQL 18 (compose) / local 14 | ✅ reachable | Tests run against a throwaway `chess_test` DB; dev DB is guarded against |

> **Decision:** the containerised path (`docker compose up`) is the primary quick
> start; local processes remain documented for iterating on one side. `pnpm` is
> not used — the frontend is npm.
