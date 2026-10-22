# ADR-007: Unit of work in the service layer + conditional version update

- **Status:** Accepted
- **Date:** 2026-10-22
- **Relates to:** DB-015, DB-016, API-019, Phase 1

## Context

`GameRepository` committed inside every method, so `GameService.submit_move` ran
two separate commits: it wrote the move row and *then* bumped the version after a
read-modify-write. Concurrency reproduced two concrete failures — a lost update
(two writers both read version V and wrote V+1) and orphan `game_moves` rows (the
move insert committed, then a rejected version write left it dangling and answered
500 instead of 409). Scattered `assert updated is not None` masked the invariant
rather than enforcing it.

## Decision

- **Repositories flush, never commit.** All `commit`/`refresh` calls were removed
  from the repository.
- **One transaction per service operation** via
  `app/core/unit_of_work.transaction(db)`: a context manager that commits on a
  clean exit and rolls back on any exception (including a failed flush, whose
  cleanup must not mask the real cause). Every service function opens exactly one
  `transaction(db)` and does all its reads/writes inside it, so a rejected move
  rolls back its own move insert.
- **Conditional UPDATE instead of read-modify-write.**
  `GameRepository.apply_state(..., expected_version=...)` issues
  `UPDATE games SET version = version + 1, ... WHERE id = :id AND user_id = :uid
  AND version = :expected` and returns `rowcount`. `rowcount == 0` means the row
  moved under us → the caller raises `StaleVersionError` (surfaced as HTTP 409).
  The `assert updated is not None` statements were deleted in favour of this.
- **`move_number`** is computed with a single `SELECT count(*)` inside the
  transaction; the new `UNIQUE (game_id, move_number)` constraint (migration
  `a1b2c3d4e5f6`) rejects collisions rather than trusting an in-memory length.

## Consequences

- Exactly one of two racing writers wins (200) and the other gets 409; no orphan
  move rows. Covered by a two-`Session`/two-thread contention test.
- The optimistic-concurrency guard is now a single WHERE clause, not application
  logic that can drift, so the two-ply human+engine write composes safely.
- Repositories are no longer independently usable outside a transaction — an
  intentional trade: the transaction boundary belongs to the use case, not the
  table.
