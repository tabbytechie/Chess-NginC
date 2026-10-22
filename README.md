# Chess NginC

A browser-based chess application: server-authoritative rules (python-chess), a
Stockfish opponent delivered as an isolated sidecar container, user accounts with
e-mail verification and password reset, PostgreSQL persistence, and a React +
TypeScript interface. A hand-written Python engine is kept as the degraded
fallback.

> **Status:** v0.2 — a playable, persisted human-vs-computer game loop
> (choose your side and difficulty, move and get an engine reply in one round
> trip, resign/undo, threefold + automatic draws, PGN export, real statistics),
> hardened auth (hashed session and recovery tokens, proxy-aware rate limits,
> CSRF), containerised deployment, and CI through a Playwright e2e job. See
> `PROJECT_CHECKLIST.md` for authoritative progress and `docs/PLAN.md` for the
> roadmap.

## What this project provides

- Fully playable standard chess via python-chess, validated and replayed
  server-side (illegal moves rejected, threefold/insufficient-material/fifty-move
  handled, optimistic-concurrency versioning).
- Player-vs-computer against **Stockfish** (remote sidecar, or a local binary, or
  the custom minimax/alpha-beta fallback via the `EngineProvider` seam) and local
  two-player on one device, at easy/medium/hard difficulty.
- Registration, login/logout, session restore, hashed bearer tokens,
  e-mail verification and password reset, saved games, move history, live
  statistics, and PGN export.
- PostgreSQL persistence with reversible Alembic migrations.
- Responsive, accessible (ARIA grid + keyboard) React + TypeScript UI.
- Automated tests (backend `pytest` with a coverage floor, frontend `vitest`,
  Playwright e2e), CI, security controls, and a hardened Compose deployment.

## Repository layout

```
apps/web/       React + TypeScript + Vite frontend
apps/api/       FastAPI backend (modular monolith)
docs/           architecture, plan, loops, agents, standards
infra/          Docker and deployment artifacts
```

> Modules are added as their functionality lands (see `docs/architecture.md`).

## Getting started

### Path A — containers (recommended)

```bash
cp .env.example .env                      # set POSTGRES_PASSWORD, SECRET_KEY, CORS_ORIGINS
docker compose up --build                 # db → migrate → engine + api → web  -> http://localhost:5173
docker compose logs api --follow          # watch for migration or startup errors
```

The `db` and Stockfish `engine` services publish **no** host port — the engine
sidecar lives on a private network and the API is its only client
(`docs/decisions/0006-stockfish-sidecar.md`). Migrations run as a one-shot
`migrate` service before `api` starts. Add `-f compose.debug.yaml --profile
debug` to expose Adminer for manual DB inspection.

### Path B — local processes

Terminal 1 (API) — needs PostgreSQL 14+ running:

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../../.env.example .env                # set database_url to a database you own
alembic upgrade head
uvicorn app.main:app --reload
```

Terminal 2 (web):

```bash
cd apps/web
npm ci
npm run dev                               # http://localhost:5173, /api proxied to :8000
```

Details in `apps/api/README.md` and `apps/web/README.md`. Tests need a
throwaway database and will refuse to run against a development one.

### Checks

```bash
cd apps/api && ruff check app tests && ruff format --check app tests && mypy app && pytest
cd apps/web  && npm run lint && npm run typecheck && npm run format:check && npm run test:run
```

## Development workflow

Every change follows the loops in `docs/development-loops.md` and reports using the format in `docs/agents.md`. See `CONTRIBUTING.md` before contributing.

## Documentation

- `docs/PLAN.md` — roadmap and milestones
- `docs/development-loops.md` — the LOOP A–H execution machine
- `docs/agents.md` — agent roles and reusable task briefs
- `docs/architecture.md` — module boundaries
- `docs/code-standards.md` — coding, testing, and review standards

## License

The project's own source is licensed under the **MIT License** — see `LICENSE`.
Third-party components carry their own licenses, disclosed in
`THIRD_PARTY_NOTICES.md`: notably python-chess (GPL-3.0-or-later) is linked into
the API, and the **Stockfish** opponent ships only as a separate, unmodified
container on a private network (never bundled into the API image, per `REL-011` /
ADR-006). The python-chess copyleft vs. MIT tension is an open legal-review item
(SEC-024); review `THIRD_PARTY_NOTICES.md` before external distribution.
