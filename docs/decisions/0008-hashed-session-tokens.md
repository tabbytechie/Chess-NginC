# ADR-008: Hashed session tokens (and the forced re-login)

- **Status:** Accepted
- **Date:** 2026-10-22
- **Relates to:** SEC-007, SEC-021, Phase 4

## Context

Sessions were stored with the **raw** bearer token in a unique indexed column
(`sessions.token`). A database read, a leaked backup, or a SQL-injection style
exposure would hand an attacker every user's live, ready-to-use cookie — the
hash was only ever applied to passwords. A session token is a bearer secret, so it
should be stored like one: irreversibly.

## Decision

- Store `token_hash = sha256(token)` (`app/auth/security.hash_token`) in a
  `String(64), unique, indexed` column; the raw token is never persisted. The
  cookie still carries the 32-byte URL-safe secret the client already holds.
- Lookups become `WHERE token_hash = :h` (`app/auth/service.py`), an exact match
  on a hex digest, so authentication cost is unchanged.
- Migration `d4e5f6a7b8c9_hashed_session_tokens` adds `token_hash`, drops `token`,
  and **truncates `sessions`**. Because the pre-image of an existing raw token
  cannot be recovered into the new column and this is pre-launch, every session is
  invalidated — a one-time forced re-login, which is the accepted cost.
- Expired-session hygiene keeps the lazy delete on `authenticate` **and** gains
  `scripts/prune-sessions.py` for a scheduled sweep, so the table cannot grow
  unbounded from abandoned sessions.

## Consequences

- A stolen database no longer yields usable session tokens (an offline
  preimage/brute-force over 256-bit secrets is infeasible).
- All users are logged out once at deploy. Shipped deliberately, alone, with a
  note in `docs/deployment.md`; acceptable only because there are no real users
  yet. Any future token-format migration must avoid truncation or provide a
  dual-read grace period.
- Session lookups key on a digest rather than the plaintext the client sends — a
  negligible hashing step per authed request.
