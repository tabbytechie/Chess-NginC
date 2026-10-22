# Chess Engine Strength & Limitations

## Who actually plays the opponent

The **shipped opponent is Stockfish**, reached through the `EngineProvider` seam
(ADR-006 / ADR-010): in Compose it runs as an isolated sidecar container on a
private network (`engine_backend=stockfish_remote`); `stockfish_local` uses a
locally-installed binary for dev; and `custom` is the pure-Python engine below,
kept only as the **degraded fallback** the circuit breaker selects when the
sidecar is unavailable. This document describes that fallback's real,
measured behaviour — it is deliberately not the primary opponent.

## The custom fallback (`app/engine/`)

A basic search-based engine:

- **Evaluation:** material only (piece values) plus terminal detection.
- **Search:** negamax with alpha-beta, depth-limited by difficulty.
- **Difficulty → depth:** `easy = 1`, `medium = 3`, `hard = 5` plies
  (`EngineDifficulty`). These are the *search* depths; the server-side
  difficulty→budget map in ADR-010 (`easy 2/300 ms`, `medium 6/700 ms`,
  `hard 12/1500 ms`) bounds **Stockfish**, and the sidecar still clamps every
  search to `depth ≤ 15 / time ≤ 1000 ms`.
- **Safety:** deadline-aware search returns the best move found so far with
  `termination="timeout"` and reports the *achieved* depth, never `legal_moves[0]`.

## Strengths

- **Correctness:** The engine only returns legal moves and correctly identifies terminal positions (checkmate, stalemate, draws).
- **Deterministic:** With the same configuration and position, the engine returns consistent results.
- **Safety:** Time limits and cancellation prevent runaway searches.
- **Test Coverage:** 222 backend tests pass, including the tactical regression
  suite `tests/test_engine_tactics.py`. It pins the fallback's measured behaviour
  across every provider that can run locally: mate-in-1 (back-rank), winning a
  free queen, winning a free rook, queen-takes-rook, and the same free-queen
  capture at `hard`. Before the Phase 2 fix the engine's fixed-POV mate constant
  combined with per-ply negamax negation **inverted the score at odd depths**, so
  it *declined* a free queen at depth 1/3/5 — a correctness bug, not a strength
  limit. The suite asserts the perspective is now consistent at depths 1/3/5, that
  a tiny budget returns a shallower-but-legal best move, and that the circuit
  breaker degrades to this fallback instead of raising.

## Stockfish reference & benchmarking (Phase 7, BEN-001..022)

- **Source:** official upstream `https://stockfishchess.org` / `https://github.com/official-stockfish/Stockfish`;
  packaged as Ubuntu `stockfish 16-1build1` (provenance recorded in `app/engine/stockfish.py`
  + `stockfish_version_label()`).
- **Licensing (BEN-003):** Stockfish is GPL-3.0. The binary is **not** distributed with this repo —
  the adapter discovers it via `STOCKFISH_PATH` or `PATH` at runtime only. Review redistribution
  obligations (provide corresponding source + license notices) before shipping any image/installer
  that bundles the binary.
- **Adapter (`app/engine/stockfish.py`, BEN-004..008):** UCI via `chess.engine.SimpleEngine`,
  hard bounds depth ≤ 15 / time ≤ 1000 ms / threads = 1 / hash ≤ 64 MB, graceful
  `StockfishUnavailableError` / `StockfishError` handling, score normalized to centipawns
  from the mover's perspective (mate → `20000 − 10·plies`).
- **Suite (`app/engine/benchmark_suite.py`, BEN-009):** versioned `v1` suite, 12 validated FEN
  positions (openings, middlegame structures, tactics, endgames).
- **Harness (`app/engine/benchmark.py`, BEN-010..013):** `compare_position()` runs both engines on
  identical FENs, records move/score/depth/nodes/time, `agreement_rate()` + `mean_score_gap()`
  metrics, `hardware_fingerprint()` per run. Degrades to custom-only when no binary is present.
- **Persistence (BEN-019):** `benchmark_runs` + `benchmark_results` tables (migration `5a0dcdb13bb3`).
- **Repeatability (BEN-022):** custom engine deterministic per config+position (tested).
- **Remaining:** head-to-head games with alternating colors + W/D/L (BEN-014..016), rating estimate
  (BEN-017, P3), benchmark user docs (BEN-021).

## Limitations

### Evaluation Function

The current evaluation is purely material-based:
- No positional considerations (piece-square tables)
- No pawn structure evaluation
- No king safety evaluation
- No mobility or activity scoring
- No endgame-specific knowledge

**Impact:** With the material-only evaluation the fallback is **tactically naive
but positionally blind**: it solves the pinned mate-in-1 and hanging-piece
fixtures above, yet it has no strategic model — no piece-square tables, pawn
structure, king safety, mobility, or endgame knowledge — so it will misjudge
positions where the best move is not a immediate gain or mate.

### Search Depth

Default depth is 3 plies (1.5 moves ahead). This is very shallow:
- Cannot see tactical combinations beyond 1.5 moves
- Misses simple 2-move tactics
- No iterative deepening to find better moves within time limits

**Impact:** Against a stronger engine or experienced player, the engine will frequently fall into tactical traps.

### Performance

Pure Python implementation without optimizations:
- No transposition table (repeated position evaluation)
- No move ordering (inefficient alpha-beta pruning)
- No quiescence search (horizon effect on captures)
- No bitboards or other low-level optimizations

**Impact:** Search speed is limited, constraining practical depth even with generous time limits.

### Estimated Strength

No formal rating has been measured (that is the benchmarking roadmap, BEN-014..017,
not yet run to a rating estimate). Judging only from the pinned behaviour above:
- **Rough level:** beginner — it reliably takes one-move tactics and mates in the
  fixtures it is tested against, but sees nothing positional.
- **Suitable for:** a gentle opponent and as the sidecar-outage fallback.
- **Not suitable for:** competitive play or analysis — use Stockfish for both.

This is an explicit estimate, not a benchmarked number; do not cite a figure as
measured until `benchmark.py --record` output backs it.

## Planned Improvements (P2)

The following improvements are marked as P2 in the checklist and would significantly increase strength:

1. **Piece-square tables (AI-006):** Add positional bonuses for pieces
2. **Move ordering (AI-009):** Sort moves to improve alpha-beta efficiency
3. **Iterative deepening (AI-010):** Search incrementally deeper within time limits
4. **Quiescence search (AI-013):** Extend search beyond captures to avoid horizon effect
5. **Transposition table (AI-014):** Cache evaluated positions to avoid redundant computation

These improvements could potentially raise the engine to ~1200-1500 ELO.

## Comparison to Stockfish

Stockfish (Phase 7) is a world-class engine (~3500+ ELO) that uses:
- Sophisticated evaluation with hundreds of features
- Very deep search (20+ plies) with aggressive pruning
- Extensive optimization (C++, bitboards, SIMD)
- Massive opening books and endgame tablebases

Our custom fallback is not intended to compete with Stockfish — and no longer
needs to: **Stockfish is the default opponent** (ADR-006). It is used for:
- Actual play against the bot at easy/medium/hard (the difficulty→budget map).
- The `benchmark.py` harness comparing custom vs. Stockfish on the versioned FEN
  suite.
- The custom engine remains only the degraded fallback when the sidecar is down.

## Usage Recommendations

The difficulty the user picks maps, per ADR-010, to a **Stockfish** search budget
(`easy` depth 2 / 300 ms, `medium` depth 6 / 700 ms, `hard` depth 12 / 1500 ms,
capped by the sidecar at depth ≤ 15 / 1000 ms). If the sidecar is unreachable the
circuit breaker falls back to the custom engine at its `easy`/`medium`/`hard`
search depths (1/3/5), so a level label is a promise about Stockfish, and the
fallback is the safety net rather than the target.
