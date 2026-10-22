# Development Loops

> The mandatory execution machine for every phase, feature, bug fix, and refactor.
> Every change runs through **LOOP A → H** and repeats until acceptance criteria pass or a genuine blocker is reached.

```
INSPECT → PLAN → IMPLEMENT → TEST → REVIEW → FIX → DOCUMENT → VERIFY → REPEAT
```

## LOOP A — INSPECT

Read before you write.

- [ ] Check `git status` and current branch.
- [ ] Read `README.md`, `PROJECT_CHECKLIST.md`, `IMPLEMENTATION_LOG.md`, `docs/architecture.md`, and relevant code.
- [ ] Determine the **actual** state; do not assume the repo is empty or correct.
- [ ] Inspect dependencies, config, migrations, tests, and existing functionality.
- [ ] Identify which checklist IDs this change affects.
- [ ] Check for duplicate functionality before creating new code.
- [ ] Note security, compatibility, and technical-debt implications.

## LOOP B — PLAN

Pick one small, independently verifiable task.

- [ ] State the acceptance criteria.
- [ ] List files expected to change.
- [ ] Identify unit / integration / e2e tests.
- [ ] Identify dependencies and prerequisites.
- [ ] Identify possible regressions.
- [ ] Define the exact command(s) that verify completion.

> Prefer small changes over large rewrites.

## LOOP C — IMPLEMENT

Write the minimum maintainable implementation.

- [ ] Follow `docs/code-standards.md`.
- [ ] Add/update types and API schemas.
- [ ] Add tests alongside the implementation.
- [ ] Handle expected failures explicitly.
- [ ] Add a migration when the schema changes.
- [ ] Keep unrelated changes out.
- [ ] No hardcoded secrets, credentials, or machine-specific paths.
- [ ] No mocks/placeholders in production code; no silently skipped requirements.

## LOOP D — TEST

Run applicable checks after every meaningful change.

**Backend:** Ruff lint → Ruff format check → type check (`mypy app`) → relevant
pytest → integration tests (when DB/API changes). CI also enforces a **coverage
floor** (`pytest --cov-fail-under`), `pip-audit`, migration **reversibility**
(`upgrade → downgrade -1 → upgrade → check`), the **OpenAPI export drift** check
(`python scripts/export-openapi.py` then `git diff --exit-code`), and
`python scripts/check-checklist.py`.
**Frontend:** ESLint → **Prettier check** → `tsc` → Vitest → production build →
the **generated-types drift** check (`npm run check:api`) → Playwright e2e
against the composed stack for critical flows.
**Database:** migration validation → constraint validation → transaction tests → persistence/recovery tests.
**AI:** legal-move validation → terminal-position tests → timeout tests → the
`tactic` regression suite across every provider → benchmark regression tests.

- Never run destructive tests against production data.
- On failure: capture the actual error, find the root cause, fix before proceeding.

## LOOP E — REVIEW

Review as an independent senior engineer.

- Does it satisfy the requirements? Any hidden assumptions?
- Can invalid data enter? Can a user access another user's data?
- Can concurrent requests corrupt a game? Can an engine exceed its budget?
- Are errors logged and returned safely? Are transactions/migrations correct?
- Are tests meaningful? Any new complexity or technical debt? Are dependencies justified?
- Run `git diff --check` and inspect the full diff.

## LOOP F — FIX

If a relevant test fails:

1. Do **not** mark complete.
2. Record the failure.
3. Reproduce it where possible.
4. Fix the root cause, not the symptom.
5. Add a regression test.
6. Re-run the failing test.
7. Re-run related tests.
8. Re-run broader checks if the change may affect other modules.
9. Update the checklist only after verification.

> Do not loop identical commands forever. If blocked by missing credentials/infra/external services, document the blocker and continue independent tasks.

## LOOP G — DOCUMENT & VERIFY

- Update `PROJECT_CHECKLIST.md`, `IMPLEMENTATION_LOG.md`, relevant architecture/API docs, and `TECHNICAL_DEBT_REGISTER.md` (if needed).
- Record exact test commands and outcomes; identify checks **not** run.
- Confirm the working tree contains only intended changes.

## LOOP H — CONTINUE

- Pick the next highest-priority task whose dependencies are satisfied.
- Repeat A–G.
- At session end, record the **next task and its acceptance criteria** so work resumes without repeating completed work.

## Definition of Done (gate)

A feature is done only when: implementation exists; acceptance criteria satisfied; tests passed (within the coverage floor); no critical regression; every CI gate green (lint/format/types/audits/migration-reversibility/OpenAPI drift/prettier/e2e/checklist-count); security/authorization reviewed; docs updated; checklist has evidence; limitations documented; change reviewed.

## Session protocol

1. Start by reading `PROJECT_CHECKLIST.md` and `IMPLEMENTATION_LOG.md`; verify the last recorded task before continuing.
2. Work in small loops; run the verification command for each.
3. End by updating the checklist/log and stating the next task + acceptance criteria.
