# Technical Debt Register

> Known debt, reasons, impact, affected modules, remediation plan, repayment trigger, status.
> Debt is honest and expected; never claim it is zero.

| ID | Description | Reason | Impact / Severity | Modules | Remediation | Repayment trigger | Status |
|----|-------------|--------|-------------------|---------|-------------|-------------------|--------|
| TD-001 | Pure-Python search will be slow at depth | Iterate quickly; python-chess for rules | Medium — limits search depth/strength | `engine/custom` | Profile; consider compiled core (C/Rust/extension) | Move latency exceeds target | Open |
| TD-002 | Docker installed (29.8.2); compose verified end-to-end | Local env now has Docker | Low — resolved | infra | Full `docker compose up` verified (db/api/web); no further infra work | n/a | Resolved |
| TD-003 | pnpm not installed; npm chosen | Tool availability | Low — package manager divergence from spec | web | Standardize once, then lockfile | Team/CI requires pnpm | Open |
| TD-004 | Stockfish licensing reviewed; binary not bundled | GPL-3.0 would infect the service if distributed | Medium — resolved for this repo | engine/stockfish | Documented apt/upstream install at deploy (REL-011); SBOM only if ever distributing the binary | If Stockfish is ever bundled | Resolved |
| TD-005 | ~~Email verification & password reset deferred~~ Built behind a sender abstraction (`ConsoleEmailSender` default, SMTP by config) | Was not needed for local dev; now shipped | Low — resolved | auth | SEC-018/019 shipped: hashed single-use recovery tokens, non-enumerating endpoints, sessions revoked on reset; a real mail provider is a config change only | n/a | Resolved |
| TD-006 | Full PGN stored/derived from moves (no cached copy) | Avoid competing representations | Low | games | Generate PGN from moves; add cache only if needed | Measured performance/recovery need | Accepted |
| TD-007 | ~~Single engine worker initially~~ Sidecar holds one persistent `popen_uci` engine per worker behind a `MAX_CONCURRENT_SEARCHES` semaphore | Keep concurrency bounded | Low — resolved for the sidecar | engine | Bounded warm pool shipped (ADR-006); the API also caps per-request search outside any DB transaction | n/a | Resolved |
| TD-008 | Disk at 99% capacity on dev machine | External environment | High — blocks builds/installs | infra/ops | Free space (user action) | Before installing dependencies | Open |
| TD-009 | npm cannot write its cache/logs under `$HOME` | Assistant file sandbox (workspace-write) blocks writes outside the workspace; npm misreports as "root-owned files" | Low — `--cache $(mktemp -d)` workaround proven; all deps already installed | web | Use temp `--cache` for future `npm install`; **no `sudo chown` needed** (ownership already correct) | Next `npm install` | Open |
| TD-010 | `uvicorn[standard]` (uvloop/httptools) not yet used | 3.14 wheel availability unconfirmed | Low — fewer prod niceties | api | Confirm wheels, then enable extras | Before production | Open |
| TD-011 | Starlette `TestClient` deprecates `httpx` in favor of `httpx2` | Upstream forward-migration | Low — test warning only today | api/tests | Migrate to httpx2 when stable | When starlette drops httpx | Open |
| TD-012 | Rate limiting is in-process (per-worker memory), not shared | No Redis in MVP scope (deliberately excluded) | Medium — **single-worker constraint**: limits are per API process, so horizontal scaling multiplies the effective budget rather than enforcing a global cap | api (deps) | Move the buckets to a shared store (Redis) when running >1 worker; the `forwarded_allow_ips` + per-class bucket design already anticipates it | Deploying more than one API worker | Accepted |

## Watched risks (from spec)

Python search performance · duplicate chess rules · inconsistent game state · duplicated API contracts · missing transaction boundaries · excessive engine concurrency · unbounded resource usage · poor special-move test coverage · authentication shortcuts · unreviewed licensing · premature microservices · overengineered abstractions · missing recovery/ops procedures.
