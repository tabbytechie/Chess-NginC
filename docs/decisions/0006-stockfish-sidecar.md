# ADR-006: Stockfish delivered as an isolated sidecar container

- **Status:** Accepted
- **Date:** 2026-10-22
- **Relates to:** REL-011, SEC-013, AI/BEN engine work (Phase 2)

## Context

The product owner chose Stockfish — not the hand-written `ChessEngine` — as the
shipped opponent. Stockfish is GPL-3.0-or-later. Bundling its binary into the API
image would pull strong copyleft into an artifact we license MIT
(`THIRD_PARTY_NOTICES.md`) and would violate the standing `REL-011` requirement
that the API image stay binary-free. Stockfish is also a heavy, stateful native
process, so per-request `popen_uci` is wasteful.

## Decision

Ship Stockfish as a **separate container** (`services/stockfish/`):

- Reachable **only** on an `internal: true` Docker network, with **no published
  port**. It mounts no database and never imports `app.*`.
- A small FastAPI service opens **one persistent** `chess.engine.SimpleEngine`
  per worker at boot, guarded by a bounded semaphore (`MAX_CONCURRENT_SEARCHES`),
  configured with `Threads`/`Hash`, and health-checked (`/healthz` on `uciok`).
- The API talks to it over `httpx` via `RemoteStockfishProvider`, which enforces
  a 3 s connect / 8 s read timeout and re-applies hard search bounds **server
  side** so a hostile client cannot request an unbounded search.
- Provider selection is a single seam (`app/engine/factory.py`, chosen by the
  `engine_backend` setting): `stockfish_remote` | `stockfish_local` | `custom`.
- `app/engine/circuit.py`: after N consecutive `EngineUnavailableError` the API
  falls back to `CustomEngineProvider` for a cooldown window and logs one warning,
  so a sidecar outage degrades instead of returning 500s. `/ready` reports the
  sidecar as `degraded`, never fatal.

## Consequences

- GPL-3.0 stays confined to its own container, distributed unmodified and invoked
  over the network as a separate work — `REL-011` is preserved.
- The `EngineProvider` protocol is now the only engine entry point; the service
  layer is backend-agnostic, and `LocalStockfishProvider` keeps native-Homebrew
  dev working without Docker.
- Extra operational surface (a second service + health gating on `depends_on`) is
  the cost; the warm pool removes spawn-per-move latency and becomes the `ANL-003`
  pool the earlier docstrings promised.
