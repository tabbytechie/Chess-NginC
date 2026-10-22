# Contributing

Thanks for contributing. This project is built incrementally and verified at every step — read this before making changes.

## Before you start

1. Read `docs/development-loops.md` (the mandatory LOOP A–H machine) and `docs/code-standards.md`.
2. Check `PROJECT_CHECKLIST.md` for the current state and pick a task whose dependencies are satisfied.
3. Run `git status` and confirm the working tree is clean.

## Commit & PR standards

Use conventional commit prefixes:

- `feat:` — new functionality
- `fix:` — bug fixes
- `test:` — tests
- `refactor:` — restructuring without behavior change
- `docs:` — documentation
- `chore:` — tooling and maintenance

Examples:

```
feat(engine): implement alpha-beta pruning
fix(game): reject illegal castling moves
test(engine): cover terminal position evaluation
refactor(api): separate game service from routes
```

Every pull request must explain:
- the change and why,
- tests performed (exact commands + results),
- any migration or security implications,
- known technical debt introduced or addressed.

## Quality gates (run before merge)

Every gate below is enforced in CI (`.github/workflows/ci.yml`) and must pass
locally before a PR is ready.

| Area | Command (from the app directory) |
|------|----------------------------------|
| Python lint/format | `ruff check app tests && ruff format --check app tests` |
| Python type check | `mypy app` |
| Python tests + coverage floor | `pytest --cov=app --cov-report=term-missing --cov-fail-under=85` (dedicated test DB only) |
| Dependency audit | `pip-audit` (backend), `npm audit --omit=dev` (frontend) |
| Migration reversibility | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head && alembic check` |
| OpenAPI contract drift (backend) | `python scripts/export-openapi.py && git diff --exit-code -- openapi.json` |
| OpenAPI types drift (frontend) | `npm run check:api` (regenerates `src/lib/api-schema.ts`, fails on diff) |
| Frontend format | `npm run format:check` |
| Frontend lint | `npm run lint` |
| Frontend type check | `npm run typecheck` |
| Frontend tests | `npm run test:run` |
| Production build | `npm run build` |
| Checklist counts honest | `python scripts/check-checklist.py` (repo root) |
| End-to-end | `docker compose up -d --build` then `npx playwright test` (the CI `e2e` job — the only gate that proves the composed stack plays a real game) |

A failed required gate prevents a PR from being ready to merge.

## Environment rules that must not regress

- **Test DB safety:** the suite drops and recreates tables between tests, so it
  must run against a throwaway database (e.g. `chess_test`), **never** the
  developer `chess` database. `conftest.py` guards this at collection time.
- **Paths with spaces:** the repository directory name contains a space
  (`Chess NginC`). Nothing may build a shebang or shell command by embedding an
  interpolated interpreter path into a one-line `#!/usr/bin/env -S …` script or an
  unquoted command — it splits at the space. Test fixtures (the fake-UCI shim) and
  scripts must pass the interpreter as a separate `sys.executable` argument and
  quote paths, so a fresh clone in a spaced directory stays green.
- **Never commit `.env`** or generated DB dumps (`backups/`, `*.sql`).

## Review checklist

- Single responsibility and clear module boundaries (no search in API, no DB in engine).
- Explicit types and validated inputs.
- Expected errors handled without hiding failures.
- Tests for normal behavior and important edge cases.
- No secrets, dead code, debug prints, or undocumented placeholders.
- No unnecessary dependencies or duplicated logic.

## Definition of clean code

Follows naming/formatting; explicit types + validated inputs; business logic separated from UI/API/persistence; expected errors handled; tests included; quality gates pass; no unnecessary deps or duplication; deliberate shortcuts documented with a repayment trigger.
