# Third-Party Notices

Chess NginC's own source is licensed under the MIT License (see `LICENSE`). The
project is built on, and in the API's case **links**, third-party components that
carry their own licenses. Those licenses are **not** relicensed or superseded by
our MIT grant — this file discloses them. Licenses and versions below were read
from the installed package metadata, not asserted from memory.

## Runtime dependencies — backend (`apps/api`)

| Package | Version | License (SPDX) | Use |
|---|---|---|---|
| python-chess | 1.999 | **GPL-3.0-or-later** | Move legality, FEN/PGN, SAN/UCI, game-terminal detection (`app/games/rules.py`, engine) |
| psycopg | 3.3.6 | **LGPL-3.0-only** | PostgreSQL driver |
| SQLAlchemy | 2.1.4 | MIT | ORM / persistence |
| Alembic | 1.20.0 | MIT | Schema migrations |
| FastAPI | 0.143.0 | MIT | HTTP API |
| Starlette | (FastAPI) | BSD-3-Clause | ASGI toolkit under FastAPI |
| Uvicorn | 0.54.0 | BSD-3-Clause | ASGI server |
| Pydantic | 2.14.0 | MIT | Request/response schemas |
| httpx | 0.28.1 | BSD-3-Clause | API → Stockfish sidecar client |
| bcrypt | 5.0.0 | Apache-2.0 | Password hashing |

## Copyleft caveat — read before distributing the API

`python-chess` is **GPL-3.0-or-later** and is imported directly into the API
process, and `psycopg` is **LGPL-3.0-only**. Linking them into a single program
means that **any distribution of the API as a combined work is governed by those
copyleft terms in addition to our MIT license** — our MIT grant covers only the
original Chess NginC source files and grants no extra rights over these
dependencies. In practice the composite backend must be distributed under terms
that satisfy GPL-3.0-or-later (source availability for the combined work, etc.).

This tension between the chosen MIT license and the linked copyleft libraries is a
known, deliberate open item tracked as **SEC-024 (third-party licensing review)**
in `PROJECT_CHECKLIST.md`. **Obtain legal review before external distribution**;
the two owner-sanctioned resolutions are (a) keep MIT and treat the copyleft
obligations as attaching to the distributed composite, or (b) relicense the
project under a GPL/AGPL-compatible copyleft so the whole work is consistently
licensed. The frontend and the isolated Stockfish container are unaffected by the
python-chess issue (the frontend does not use it; the API image does not ship
Stockfish).

## The Stockfish opponent (separate container)

- **Stockfish** is distributed under **GPL-3.0-or-later** and is **never bundled
  into the API or web images** (decision `REL-011`, recorded as
  `docs/decisions/0006-stockfish-sidecar.md`). It runs only in its own container
  (`services/stockfish/`), **unmodified**, installed from the apt package
  (`stockfish`, version pinned in `app/engine/stockfish.py` provenance
  constants), and is invoked over a private Docker network via UCI — so the
  strong-copyleft engine stays a separate work communicated to, not linked into,
  our code.
- The `chess` library's `chess.engine` glue used to drive Stockfish is likewise
  GPL-3.0-or-later and lives only in the sidecar.

## Runtime dependencies — frontend (`apps/web`)

| Package | License (SPDX) |
|---|---|
| react / react-dom | MIT |
| react-router-dom | MIT |
| framer-motion | MIT |
| clsx | MIT |
| lucide-react | ISC |
| vite | MIT |

## Development / tooling (not shipped)

Ruff (MIT), mypy (MIT), pytest (MIT), pip-audit (Apache-2.0), ESLint (MIT),
Prettier (MIT), TypeScript (Apache-2.0), Vitest (MIT), openapi-typescript (MIT),
Playwright (Apache-2.0), PostgreSQL (PostgreSQL License, essentially
BSD/MIT-like). These are build/test-time only and are not linked into a shipped
artifact.

## Notices

Each dependency's full license text ships inside its own distribution
(`.venv/.../*.dist-info/` on the backend, `node_modules/*/LICENSE` on the
frontend). This file is a summary for convenience and is not a substitute for the
license texts themselves, which govern.
