# API Reference (API-020)

> Base URL: `/api/v1`. All responses are JSON except the PGN download. Errors use
> the envelope `{ "detail": "<message>" }` (SEC-016/SEC-017: no hashes, tokens, or
> stack traces). The machine-readable contract is `GET /openapi.json`, and the
> frontend types are **generated** from it (see [OpenAPI](#openapi) below).

## Conventions

- **Auth:** session cookie `session_token` (HttpOnly, SameSite=Lax). Endpoints
  marked 🔒 require it; otherwise `401 {"detail": "Not authenticated"}`.
- **CSRF:** state-changing (POST) endpoints require a same-origin
  `Origin`/`Referer` (SEC-008); the origin is compared on `scheme://netloc`, so a
  legit `Referer: http://localhost:5173/games/7` is accepted. Cross-origin POSTs
  get `403`. Requests carrying neither header (curl, tests) pass through.
- **Rate limits:** per client IP, split into independent buckets so a flood on
  one class cannot starve the others — `auth` 10 req/min, `engine` 60 req/min,
  `writes` (game mutations) 120 req/min. `429` when a bucket is exceeded. The
  real client IP is taken from `X-Forwarded-For` **only** when the socket peer is
  a configured proxy (`forwarded_allow_ips`), so a client cannot spoof its bucket.
- **Ownership:** games are scoped to the caller; foreign/unknown ids return `404`
  (indistinguishable, no enumeration).
- **Concurrency:** game mutations carry `expected_version`; a mismatch returns
  `409` and the client re-fetches and replays its intent.

## Status codes

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Successful reads and actions |
| 201 | Created | Registration, game creation |
| 202 | Accepted | Recovery requests (verification resend, password reset) |
| 204 | No Content | Logout (cookies cleared) |
| 400 | Bad Request | Invalid email/password, invalid or expired recovery link |
| 401 | Unauthorized | Missing/expired session, bad credentials |
| 403 | Forbidden | Cross-origin state-changing request |
| 404 | Not Found | Unknown id or foreign-owner resource |
| 409 | Conflict | Stale `expected_version`, action on finished game |
| 422 | Unprocessable Content | Illegal/unparsable move, wrong side to move, bad draw claim |
| 429 | Too Many Requests | Rate limit exceeded for the route's bucket |
| 503 | Service Unavailable | Engine saturated/unavailable (`Retry-After: 2`); not-ready probe |

## Health

| Method & Path | Auth | Description |
|---------------|------|-------------|
| `GET /health` | — | Liveness: `200 {"status":"ok"}` while the process is up |
| `GET /ready` | — | Readiness gate (REL-007). `200` when the DB answers; `503` when it does not. Body `{status, database, engine}` |

`/ready` reports the opponent backend in `engine` as `builtin` (in-process
custom), `local` (host Stockfish binary), or `up`/`degraded` (sidecar ping). The
engine field is **informational** — a sidecar outage degrades the opponent to the
fallback but never flips the endpoint to `503`; only an unreachable DB does.

## Auth

| Method & Path | Auth | Description |
|---------------|------|-------------|
| `POST /auth/register` | — | `201` + sets session. Body `{email, password}`. Best-effort mails a verification link. `400` on duplicate/invalid |
| `POST /auth/login` | — | `200` + sets session. `401` with a generic message (timing-safe: always runs a hash verify) |
| `POST /auth/logout` | 🔒 | `204`, revokes the session and clears cookies. **Idempotent** — always `204` + clears cookies, even without a session |
| `GET /auth/me` | 🔒 | `200 {id, email, email_verified}` |

`UserResponse` never includes the password hash.

### Account recovery

All four are rate-limited (`auth` bucket) and CSRF-guarded. The request-style
endpoints return a **uniform** reply so they cannot enumerate accounts — the body
and status are identical whether or not the email exists.

| Method & Path | Auth | Description |
|---------------|------|-------------|
| `POST /auth/verify-email` | — | Body `{token}`. `200` on success; `400` on invalid/expired link. Reply reflects token validity, not account existence |
| `POST /auth/resend-verification` | — | Body `{email}`. `202` with a uniform message for any email |
| `POST /auth/request-password-reset` | — | Body `{email}`. `202` with a uniform message; never reveals if the email exists |
| `POST /auth/reset-password` | — | Body `{token, password}`. `200` on success (and revokes **all** outstanding sessions); `400` on invalid/expired link |

Recovery tokens are 32-byte URL-safe secrets, stored **hashed**, purpose-scoped,
single-use (`consumed_at`), with a TTL (24 h verification / 30 min reset).

## Games (all 🔒)

| Method & Path | Description |
|---------------|-------------|
| `POST /games` | Create a game. Body `{mode: "local"\|"computer", player_color: "white"\|"black"\|"random", engine_level: "easy"\|"medium"\|"hard"}` (defaults `local`/`white`/`medium`) → `201 GameResponse`. `random` resolves server-side; a computer game where the player draws Black returns with the engine's opening already played |
| `GET /games` | Page of the caller's summaries, newest first. Query `status`, `limit` (1–100, default 20), `offset` (≥ 0). Returns `GameListResponse` (see below) — one aggregate query, no per-row move fetches |
| `GET /games/{id}` | One full `GameResponse` incl. ordered moves; `404` if unknown/foreign |
| `POST /games/{id}/moves` | Body `{uci, expected_version}`. Validates legality (422), version (409), terminal sync. In `computer` mode it plays the human ply **and the engine's auto-reply** in one atomic pair and returns both plies — no second round trip. `422` if it is not the human's turn |
| `POST /games/{id}/undo` | Body `{expected_version}`. In `computer` mode removes the trailing ply pair so the human is on move again; one transaction |
| `POST /games/{id}/resign` | Marks `resigned`, records the winner/result; `409` if already finished |
| `POST /games/{id}/draw-claim` | `422` unless the position supports a draw claim (e.g. threefold, detected by replaying stored moves) |
| `POST /games/{id}/engine-move` | Computer games, engine's turn only. Body `{expected_version}` — **no client-set depth/time**; the server maps the game's difficulty to a bounded budget. `503` + `Retry-After` if the engine is saturated/unavailable (never a silent 500) |
| `GET /games/{id}/pgn` | PGN download (`application/x-chess-pgn`) with `Content-Disposition: attachment; filename="game-<id>.pgn"`; standard headers + result |
| `GET /stats` | Aggregate `StatsResponse` (`by_mode`), one query (API-021) |

### `GameResponse`

`id, mode, status, fen, version, player_color, engine_level, result, winner?,
end_reason?, in_check, move_count, moves[]`. `in_check` is derived server-side
(from the python-chess board) so the frontend never guesses; `winner`/`end_reason`
are present only once the game is finished; `result` is a PGN result token
(`1-0` / `0-1` / `1/2-1/2` / `*`).

### `GameListResponse` (pagination contract)

`{ items: [GameSummaryResponse], total, limit, offset }`. `items` rows are
summaries (`id, mode, status, player_color, engine_level, result, winner?,
version, move_count, last_played_at`) — no move payloads. `total` is the full
count matching the filter, so the client paginates by advancing `offset` until
`offset + items.length >= total`.

### `StatsResponse`

`{ by_mode: { "<mode>": { wins, losses, draws, finished, total } } }`, keyed by
game mode.

### Move flow

1. Client sends `{uci, expected_version}` where `expected_version` is the
   `version` from its last `GameResponse`.
2. Server validates legality, persists the move, applies the engine reply (in
   `computer` mode), derives terminal status/result, and bumps `version` — all in
   one transaction per write, with the search running **outside** any open DB
   transaction (ADR-007).
3. Client retries on `409` by re-fetching and replaying intent.

## OpenAPI

- Machine schema: served at `/openapi.json` and checked into
  `apps/api/openapi.json`; regenerate with
  `python scripts/export-openapi.py` (validated by `tests/test_openapi.py`). CI
  fails on drift.
- Frontend types: generated into `apps/web/src/lib/api-schema.ts` via
  `openapi-typescript` (`npm run gen:api`); `api-types.ts` is a thin overlay that
  re-exports them and tightens the enum unions. CI asserts the generated file
  matches the backend with `npm run check:api` (API-022).
