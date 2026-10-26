# Phase 13 — Robustness & Concurrency Plan

> Plan to close the weaknesses found in the architecture review (W1–W11), so the
> single-replica, offline-CI design becomes a launch-hardened one without giving up
> any invariant. Invariants held through all stages: offline-hermetic tests, CI gates
> = done, ownership authorization (404-on-foreign) unchanged, server owns every
> outcome, engine/voice/LLM each stay behind their single seam, and rate limiting keeps
> the transport-agnostic `check_*` signatures.
>
> Ordering is by **leverage per risk**. Stage 13A are surgical, low-risk fixes that
> raise the ceiling immediately. Stage 13B is the structural one (job queue). Stage 13C
> is scale-out readiness gated on its trigger, exactly like RL-005/TD-012 already are.
> A "trigger" column means the same thing as the debt register: the work is designed
> now and paid for when a real condition, not a calendar, demands it.

## The weaknesses (review findings) — mapped to stages

| # | Weakness | Evidence | Stage |
|---|----------|----------|-------|
| W1 | A 12 s CPU engine batch holds a pooled DB connection; pool is untuned defaults | `core/database.py:112` `create_engine(url, echo=False)`; `reviews/service.py` holds `db` across `analyse_game` | 13A |
| W2 | Scale-out blocked by design: in-process islands (lobby, sockets, limiters, cloud budget) | TD-012; `deps.py` module buckets; `cloud_stockfish` counter | 13C |
| W3 | Per-IP limiting reads `request.client.host`, meaningless behind a proxy | `deps.py:47` | 13A (launch blocker) |
| W4 | Review is synchronous → multi-minute request for long games | TD-013/ANL-008; `review_rate_limit_per_hour` papers it | 13B |
| W5 | No eval cache → same FEN re-searched on force-reruns / coach what-ifs | ANL-005 open | 13B |
| W6 | Engine concurrency tiny (`ENGINE_MAX_CONCURRENCY=2`), queue invisible | `.env`; TD-007 accepted | 13B/13C |
| W7 | Recompute-where-cacheable (achievement stats; no HTTP cache on immutable review) | TD-015; `GET /review` | 13A (HTTP cache) / 13C (stats) |
| W8 | uvloop/httptools not enabled | TD-010 | 13A |
| W9 | Quality ceilings (fixed grading bands, book transit moves, pattern-only drills) | TD-016/018/019 | 13D |
| W10 | One frontend bundle (~383 kB) loads coach + drills UI on every page | `vite build` | 13A |
| W11 | Operational tax: `.env` CWD-relative footgun; local/CI DB drift class | repeated; alembic ritual | 13A |

## Stage 13A — Harden the request path (surgical, low-risk) — this pass

| ID | Task | Status | Notes |
|----|------|--------|-------|
| RB-001 | DB pool tuning: `pool_size`/`max_overflow`/`pool_pre_ping`/`pool_recycle` from settings | [x] | W1; defaults were never set. pre_ping kills "server gone away" after a DB restart; recycle clears LB idle timeouts. Sized for the single replica, not guessed |
| RB-002 | Release the DB connection during the review engine batch | [x] | W1; replay+validate while connected, `commit()` (returns the connection), then search+build on detached plain scalars, then a short write transaction. Turns ~12 s held → ~50 ms held. Needs `_Ply` to carry scalars, not the ORM row |
| RB-003 | Startup preflight log: resolved env file, engine mode (local/cloud/none), voice mode, without any secret | [x] | W11; the `.env`-relative footgun becomes self-evident at boot instead of via a 503 later. Never prints a key value (QA-019) |
| RB-004 | Trusted-proxy client IP for limiters (`trust_proxy_headers` + `trusted_proxy_cidrs`) | [x] | W3 **launch blocker**; default OFF → today's behavior byte-for-byte (tests stay green); when ON and the peer is a trusted CIDR, walk XFF from the right to the closest hop that is not itself a trusted proxy (nginx `real_ip_recursive` — the shipped `$proxy_add_x_forwarded_for` *appends* the real client, so leftmost is client-forgeable); XFF from an untrusted peer is ignored entirely (spoof guard) |
| RB-005 | `ETag`/`Cache-Control` on `GET /review` | [x] | W7; the validator is an md5 of the exact bytes served, so it can never go stale across processes or a book/annotation deploy, and needs no writer-side memo; a `304` skips sending the (possibly large) body. POST path stays uncacheable |
| RB-006 | Lazy-route the heavy pages (Review / Learn / Online / Achievements / Lobby) | [x] | W10; dashboard first paint stops paying for the coach panel + 829-drill UI. Needs a Suspense boundary + a loading state |
| RB-007 | `uvicorn[standard]` (uvloop/httptools) | [ ] | W8; TD-010. **Blocked on pinning uvloop/httptools in `requirements.txt` for py3.12-linux** and re-verifying the hermetic build — kept open until the lockfile lands, so the container build never breaks. Frontend-gate determinism (raised RTL async ceiling) landed alongside 13A |

## Stage 13B — Structural: reviews off the request (ANL-008 / TD-013) — trigger: any real game > ~40 plies

| ID | Task | Notes |
|----|------|-------|
| RB-010 | `review_jobs` table (status, progress 0..N, payload ptr, error, timestamps) + migration | the durable queue is Postgres, not a new broker — one source of truth (D13 precedent) |
| RB-011 | `POST /review` enqueues and returns `202 {job_id}`; worker owns the warm engine in a bounded pool (fixes W4+W6) | request thread released in ms; the engine worker is a small fixed pool so `ENGINE_MAX_CONCURRENCY` becomes real admission control, not silent queue |
| RB-012 | `GET /review/{job_id}/progress` + a `GET /review` that serves when done | the UI animates the tour as plies land instead of blocking |
| RB-013 | Eval cache keyed `(fen, depth, multipv, movetime)` → `engine_evals` (ANL-005) | speeds force-reruns, coach what-ifs, review-mined drills; behind the existing provider seam so cloud+local share it |
| RB-014 | Loosen the hourly review bucket once the request no longer holds the engine | RL-001 was protecting a synchronous cost that RB-011 removes; re-tune, keep `Retry-After` |

## Stage 13C — Scale-out readiness (trigger: a 2nd API replica)

| ID | Task | Notes |
|----|------|-------|
| RB-020 | Redis limiter backend behind identical `check_*` signatures (= RL-005/TD-012) | routers never change; the whole reason the seams were kept |
| RB-021 | Move lobby queue + socket hub to Redis pub/sub | restarts stop dropping pairings; games already safe in Postgres |
| RB-022 | Move the cloud daily-unit counter to Redis | today it is per-process, so N replicas each under-count the shared 2,000-unit pot and discover the cap via upstream 402/429 |
| RB-023 | Incremental per-player achievement counters or a short-TTL `compute_stats` cache | TD-015 aggregation cost grows with history; runs only on terminal transitions today |

## Stage 13D — Quality ceilings (each behind an existing seam)

| ID | Task | Notes |
|----|------|-------|
| RB-030 | Rating/phase-aware grading bands behind the classifier seam | TD-016; finishes CLS-001 by grading on win%-drop (model already exists, display-only) |
| RB-031 | Key intermediate opening-book positions (most-specific-name-wins) | TD-018; `book.lookup_epd` already isolates the change |
| RB-032 | Local hot-seat games write reason-only terminal ledger rows | TD-014; makes result/streak ladders live without awarding points |
| RB-033 | Engine-verified drill alternatives (offline authoring pass); keep `verify_all()` deterministic in CI | TD-019; removes the "good move marked wrong" trust event without engine-at-grade-time |
| RB-034 | pgvector blend behind the `recall` seam | TD-020; **stay deferred** until a stored-review question is demonstrably missed on wording |
| RB-035 | Fair-play threshold calibration after real flag volume; sampled live sweeps only if player-safety demands | TD-022/023; raw signals already stored so re-tune is pure config |

## Stage 13E — Durability & recovery (data a restart cannot rebuild)

The "do the DBs have replicas to fall back on?" question resolves here, not in 13C.
There is a single Postgres, no read replica, no failover — the right call at this
scale — but *no replica must never mean no recovery*. A replica does not protect you
from a bad migration or a dropped table (it replicates the mistake); a tested backup
and a WAL you can replay to does. And the cheap 80% of what a replica buys — a peer
that outlives the primary's disk — is a **managed** provider's virtual endpoint, which
this app already reaches through one `database_url` + `pool_pre_ping` (RB-001), so it
is a config flip, not code. 13E is therefore durability, deliberately not redundancy;
read replicas / multi-AZ stay deferred until an availability SLA is actually sold.

| ID | Task | Notes |
|----|------|-------|
| RB-041 | Scheduled backup + **restore-TEST** (= REL-004/REL-005) | [x] landed; `scripts/backup-db.sh` (`pg_dump -Fc` + `.dump.meta` sha256/alembic/row-count sidecar) chains to `scripts/verify-backup.sh` (restores the newest dump into a throwaway DB and asserts against the sidecar, non-zero on mismatch); `scripts/backup-cron.example` wires them nightly + a monthly **oldest-backup** DRILL. An untested backup is not a backup |
| RB-042 | Point-in-time recovery (= REL-018) | [x] landed, **opt-in** (default stack untouched); `compose.pitr.yaml` archives WAL to `./wal-archive`; `scripts/pitr-basebackup.sh` + `scripts/pitr-restore.sh` replay to any instant in a throwaway `:5433` container, **never over live**; `pgbackrest.conf.example` is the prod path (encryption/retention/incremental). Retire once RB-040 gives provider PITR |
| RB-040 | Managed HA Postgres endpoint (RDS/Neon/Supabase/Cloud SQL) | [ ] **trigger: paid launch**; flip `database_url` to the provider virtual endpoint — no code change (one URL + `pool_pre_ping` already). The cheap 80% of a replica without operating one; hand-rolled PITR (RB-042) retires behind provider backups |

## Testing & gates (every slice)

Backend: ruff check + format, mypy, `alembic upgrade head` + `check` on a fresh
throwaway DB, full `pytest`. Frontend: eslint, `tsc --noEmit`, vitest, `vite build`,
prettier. New behavior gets a hermetic test each: RB-002 asserts the review payload is
byte-identical to before (grading is the app's most sensitive path); RB-004 asserts the
limiter keys on XFF only when the peer is a trusted CIDR and ignores a spoofed header
otherwise; RB-005 asserts a stable `ETag` + `304` on an unchanged review.

## Definition of "robust" for this pass

Stage 13A alone removes the two accidental ceilings (untuned pool + connection held
across CPU) and the launch blocker (proxy-IP limiting), makes the config footgun
self-diagnosing, and shrinks the first paint — all green, all behind existing seams.
13B–D are designed to the same seams and stay trigger-gated, which is the point: we do
not add a queue, Redis, or embeddings until a real condition needs them, exactly the
discipline that made 12A cheap to land. 13E is the exception that proves the rule: it
landed now (not gated) because a tested backup and an opt-in WAL replay are cheap, have
no live trigger to wait on, and guard the one subsystem a restart cannot rebuild — while
its redundancy half (RB-040 managed endpoint, and read replicas behind it) stays
trigger-gated until an SLA is actually sold.
