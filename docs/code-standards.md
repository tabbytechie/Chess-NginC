# Code Standards

Mandatory standards for every feature. These make the project correct, maintainable, and reviewable.

## Python (backend & chess AI)

- Follow PEP 8.
- Type hints on public functions and domain interfaces.
- Ruff for linting and formatting; mypy (or Pyright) for type checking.
- pytest for unit and integration tests; Hypothesis for property-based tests.
- Keep chess search algorithms independent of FastAPI routes and database code.
- Avoid circular imports; no broad exception suppression.
- Descriptive names, focused functions, explicit error handling.

## TypeScript + React (frontend)

- TypeScript `strict` mode; avoid `any`.
- Use discriminated unions for game modes and states.
- ESLint and Prettier; Vitest + React Testing Library.
- Functional components; small, reusable modules.
- Keep API access out of presentation components.
- Validate external input at runtime; avoid duplicated sources of truth.
- Handle loading, failure, and empty states explicitly.

## PostgreSQL (data)

- Alembic migrations only (no `create_all` in production).
- Foreign keys, unique constraints, and indexes on lookup/ownership columns.
- Transactions for move submission and game-state updates.
- Never store plaintext passwords; never commit secrets.
- Keep database queries out of chess-engine algorithms.

## Code quality principles

| Principle | Application |
|-----------|-------------|
| Single responsibility | Each module has one clear job |
| DRY | Reuse genuinely shared logic; no premature abstractions |
| KISS | Simplest design that meets requirements |
| Explicit contracts | Type hints, API schemas, clear signatures |
| Fail safely | Validate moves, inputs, permissions, engine limits |
| Testability | Core logic testable without starting the whole app |
| Maintainability | Descriptive names, short functions, focused modules |
| Security by default | Validate inputs, protect sessions, enforce ownership |

## Naming conventions

| Item | Convention | Example |
|------|-----------|---------|
| Python files/functions | snake_case | `search_position.py` |
| Python classes | PascalCase | `ChessEngine` |
| TS variables/functions | camelCase | `submitMove` |
| React components | PascalCase | `ChessBoard.tsx` |
| Constants | UPPER_SNAKE_CASE | `MAX_SEARCH_DEPTH` |
| API routes | lowercase, plural | `/api/v1/games` |
| DB tables | snake_case, consistent | `game_moves` |
| Test files | descriptive | `test_move_validation.py` |

## Layering (the example)

Bad — HTTP, rules, AI, and DB in one endpoint:

```python
@app.post("/move")
def move(data: dict):
    # validate, update board, search AI move, save to DB here
    ...
```

Good — responsibilities separated:

```python
def submit_move(game: Game, move_uci: str, rules: ChessRules) -> Game:
    move = rules.parse_legal_move(game.position, move_uci)
    return game.apply_move(move)
```

The API layer validates and calls the service; the service uses the rules adapter; a repository persists the result in a transaction.

## Enforced gates (not aspirational)

These are CI-blocking, not suggestions — a change is not "done" until all pass:

- **Backend:** `ruff check`/`ruff format --check`, `mypy app`, `pytest` with a
  coverage **floor** (`--cov-fail-under`, ratcheted up from the measured baseline),
  `pip-audit`, and migration **reversibility** (`upgrade → downgrade -1 → upgrade →
  check`).
- **Frontend:** `prettier --check` (a real gate, not just a claimed convention),
  `eslint`, `tsc --noEmit`, `vitest run`, `npm run build`, and the **OpenAPI drift**
  check (`npm run check:api`) that regenerates `api-schema.ts` from `openapi.json`.
- **Contract source of truth:** frontend types are **generated** from the backend
  OpenAPI schema, never hand-maintained against it. A schema change must re-export
  `openapi.json` (`python scripts/export-openapi.py`) or CI fails on the diff.
- **Docs honesty:** `python scripts/check-checklist.py` recomputes the checklist
  counts so the summary cannot drift from the rows.
- **E2E:** the CI `e2e` job runs Playwright against the composed stack — the only
  gate that proves API + web + engine sidecar work together.

## Test safety & portability

- Tests must never touch the developer database; they run on a throwaway DB and
  drop/recreate tables between cases (`conftest.py` guards this at collection).
- **Paths with spaces:** the repo directory name contains a space. Fixtures and
  scripts must not interpolate an interpreter path into a one-line shebang or an
  unquoted shell command (it splits at the space); pass `sys.executable` as a
  separate argument and quote paths, so a fresh clone stays green.

## Definition of clean code

A feature is clean when it: follows naming/formatting; has explicit types and validated inputs; keeps business logic separate from UI/API/persistence; handles expected errors without hiding them; includes tests for normal and edge cases; passes quality gates; avoids unnecessary dependencies and duplication; and documents any deliberate shortcut with a repayment trigger.
