# ADR-010: Server-side difficulty-to-budget map

- **Status:** Accepted
- **Date:** 2026-10-22
- **Relates to:** API-012, SEC-013, Phase 2 / Phase 3

## Context

`EngineMoveRequest` used to carry client-set `max_depth` / `max_time_ms`, which
made the opponent's strength a request parameter: any client could ask for an
expensive search, and "difficulty" had no stable meaning. `EngineDifficulty`
(`EASY=1/MEDIUM=3/HARD=5`) existed in the engine domain but was mapped to nothing
concrete.

## Decision

Strength comes from the **game row**, never the request:

- `games.engine_level` (`easy` | `medium` | `hard`, migration `c3d4e5f6a7b8`)
  is chosen at create time and persisted.
- `app/engine/domain.budget_for()` is the single map from a game's level to a
  bounded `SearchBudget(max_depth, max_time_ms)`:

  | Level  | depth | time budget |
  |--------|-------|-------------|
  | easy   | 2     | 300 ms      |
  | medium | 6     | 700 ms      |
  | hard   | 12    | 1500 ms     |

- `max_depth` / `max_time_ms` were **removed from the public request schema**;
  `EngineMoveRequest` now carries only `expected_version`. Unknown levels fall
  back to `medium`.
- The budgets are deliberately below the sidecar's hard caps
  (`STOCKFISH_MAX_DEPTH = 15`, `STOCKFISH_MAX_TIME_MS = 1000`) — the sidecar still
  clamps every search server-side, so even a mis-set level cannot exceed the box.

## Consequences

- Difficulty is a product decision with one definition of truth, applied the same
  whether the backend is the remote sidecar, a local binary, or the custom
  fallback.
- The public API surface shrinks (no tunables to abuse), which simplifies rate
  limiting and the per-user concurrency cap on `/engine-move`.
- Latency stays bounded (≤1.5 s of nominal search plus httpx timeouts), and the
  UI's "thinking" state covers the worst case.
