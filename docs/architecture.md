# Architecture

> Modular monolith API + one React frontend + one PostgreSQL database, plus a
> **separate Stockfish sidecar container** reachable only on a private Docker
> network. Backend packages are `auth`, `games`, `engine`, `api`, `core`,
> `models`, `repositories`.

## System topology

```
Browser
  │  HTTP /api/v1
  ▼
web (nginx, non-root)  ── frontend network ──▶ api (FastAPI, non-root)
                                                 │            │
                                    backend net  │            │ engine net (internal, no egress)
                                                 ▼            ▼
                                       db (PostgreSQL)   engine sidecar (Stockfish, unmodified)
                                                 ▲
                                    migrate (one-shot `alembic upgrade head`) runs before api
```

The `engine` network is `internal: true` — the sidecar publishes no port and has
no internet egress; the API is its only client, and the sidecar never mounts the
DB or imports `app.*` (ADR-006).

## API layering

```
api/v1  routes · schemas · deps (auth, rate-limit, CSRF)      — no chess algorithms
   │
   ├── auth     accounts · sessions · tokens · email senders
   ├── games    domain · rules (python-chess) · service · repository
   ├── engine   provider seam · custom · local/remote Stockfish · circuit · benchmark
   └── core     database · unit_of_work · observability · clock
                       models  repositories   →  PostgreSQL
```

## Engine provider selection (ADR-006 / ADR-010)

```
                         build_engine_provider(settings)  by `engine_backend`
                                    │
        stockfish_remote ──▶ RemoteStockfishProvider ──httpx──▶ sidecar (bounds re-applied)
        stockfish_local  ──▶ LocalStockfishProvider  ─────────▶ local binary
        custom           ──▶ CustomEngineProvider    ─────────▶ ChessEngine (fallback)

        circuit.py: after N consecutive EngineUnavailableError, wrap →
        fall back to CustomEngineProvider for a cooldown window (never a 500).
        difficulty (game row) → SearchBudget via budget_for(); client cannot set it.
```

## Module responsibilities

| Module (package) | Owns | Must NOT own |
|--------|------|--------------|
| `games` | Legal moves, turns, results, FEN/PGN, game service, repository, stats | AI search or HTTP handling |
| `engine` | Provider seam, custom search/eval, Stockfish adapters, circuit, benchmark | User accounts or DB access |
| `auth` | Password hashing, sessions, recovery tokens, email senders, validators | Chess rules |
| `repositories` | Persistence + conditional-update queries (flush only, no commit) | Committing transactions or business rules |
| `core` | Engine/session factory, unit of work, observability, clock | Domain logic |
| `api` | HTTP schemas, status codes, deps, request handling | Core chess algorithms |
| `web` | User interactions and visual state | Trusted game outcomes |

> The **analysis / classification / tactics / coaching** modules named in early
> design do **not exist** — they are the post-MVP Phase 10 roadmap in
> `PROJECT_CHECKLIST.md` and are intentionally unbuilt.

## Key boundaries

- The **API** never contains chess-search algorithms.
- The **engine** never does HTTP-to-the-client or database queries; the
  `RemoteStockfishProvider` speaks HTTP to the sidecar, but no engine code opens a
  DB session or holds a transaction during a search (ADR-007).
- The **sidecar** never mounts the DB and never imports `app.*` (ADR-006).
- The **frontend** never determines authoritative outcomes or validates AI moves.
- Repositories **flush but never commit**; each service operation owns exactly one
  `transaction(db)` unit of work (ADR-007).
- Use **dependency injection** to provide engines and repositories to services.
- Versioned API under `/api/v1`; all contracts explicit, validated, documented —
  and the frontend types are **generated** from `openapi.json` (API-022).

## Rules & engine split

- `python-chess` supplies legal move generation and position management.
- Our AI supplies evaluation and search only.
- Never write a second, independent rules engine.

## Proposed repository layout

```
apps/web/            React + TypeScript + Vite
apps/api/            FastAPI app, alembic migrations, tests, scripts
services/stockfish/  Stockfish sidecar container (FastAPI + UCI, no DB, no app.*)
docs/                architecture, plan, loops, agents, standards, decisions
infra/               Docker and deployment artifacts
scripts/             maintenance/utility scripts
.github/             CI workflows (backend, frontend, images, e2e)
compose.yaml         local Docker Compose (+ compose.dev.yaml, compose.debug.yaml)
```

> This is a logical structure, not a requirement to create every folder on day one. Modules are added as functionality lands. Deviations are documented here.

## Decisions log

| # | Decision | Status | Note |
|---|----------|--------|------|
| D1 | Use python-chess for rules; own search algorithm | Accepted | No duplicate rules engine |
| D2 | Authenticated games saved to PostgreSQL from the first playable version | Accepted | "Local two-player" = who plays, not where state lives |
| D3 | Stockfish isolated behind the engine interface, bounded execution | Accepted | Full record: ADR-006 (sidecar container, `REL-011`) |
| D4 | npm as JS package manager (pnpm not installed) | Accepted | Frontend uses npm; `legacy-peer-deps` for the codegen tool peer |
| D5 | Docker Compose for local dev + deployment; local-Postgres fallback documented | Accepted | Docker installed; primary quick start is `docker compose up` |

## Decision records

Full ADRs live in `docs/decisions/`:

- **ADR-006** Stockfish sidecar container and `REL-011` GPL compliance
- **ADR-007** Unit of work in the service layer + conditional version update
- **ADR-008** Hashed session tokens (and the forced re-login)
- **ADR-009** Sender-agnostic, hashed account-recovery tokens
- **ADR-010** Server-side difficulty-to-budget map
