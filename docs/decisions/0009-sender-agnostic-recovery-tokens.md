# ADR-009: Sender-agnostic, hashed account-recovery tokens

- **Status:** Accepted
- **Date:** 2026-10-22
- **Relates to:** SEC-013, SEC-018, SEC-019, Phase 4

## Context

Email verification and password reset must ship now so the product is
launch-ready, but the outbound email provider is **not** decided yet (SMTP relay
vs. an API like Resend). Building the flow against a specific mailer would couple
the core to an unchosen dependency. Recovery tokens are also long-lived bearer
secrets, so they inherit the same "store like a password" rule as sessions
(ADR-008). Finally, `settings.secret_key` previously had no real job.

## Decision

- **Storage:** one `auth_tokens` table (migration `e5f6a7b8c9d0`) — `id`,
  `user_id` FK `ON DELETE CASCADE`, `purpose` (`CHECK IN
  ('email_verification','password_reset')`), `token_hash` (unique, indexed),
  `expires_at`, `consumed_at`, `created_at`.
- **`app/auth/tokens.py`:** the user-facing secret is a 32-byte URL-safe token;
  only an **HMAC-SHA256 digest keyed by `settings.secret_key`** is stored —
  `_derive()` gives `secret_key` its production purpose. Tokens are
  **purpose-scoped**, **single-use** (`consumed_at`), and TTL-bound (24 h
  verification / 30 min reset). Issuing a token retires prior unconsumed tokens of
  the same purpose; `consume_token` rejects unknown / consumed / expired /
  wrong-purpose tokens uniformly.
- **`app/auth/email.py`:** an `EmailSender` `Protocol` with
  `send(to, subject, body)`. `ConsoleEmailSender` is the default (logs the link,
  so dev works with zero config); `SmtpEmailSender` activates only when
  `smtp_host` is set. `build_email_sender()` picks between them — the recovery
  flow never names a concrete provider.
- **Endpoints** `POST /auth/verify-email`, `/resend-verification`,
  `/request-password-reset`, `/reset-password`: all rate-limited and all returning
  a **uniform 202/204** so they cannot be used to enumerate accounts; reset
  consumes all outstanding sessions for the user. New settings land in `Settings`
  **and** `.env.example` together.

## Consequences

- The recovery feature is provider-independent; switching mailers is a config
  change, not a code change.
- A leaked `auth_tokens` table yields only HMAC digests, useless without
  `secret_key` — so `secret_key` is now a genuine secret that must be stable
  (rotating it invalidates outstanding reset/verification links).
- Uniform replies + `ConsoleEmailSender` default mean the happy path is real in
  dev (the URL is printed) while remaining non-enumerating in prod.
