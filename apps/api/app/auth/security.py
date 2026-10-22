"""Password hashing (bcrypt) and session-token generation."""

import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt

from app.core.clock import utc_now
from app.core.database import settings

# bcrypt truncates passwords at 72 bytes; reject longer inputs explicitly
# rather than silently truncating.
MAX_PASSWORD_BYTES = 72

# Session tokens: 256-bit entropy, URL-safe for cookie transport.
TOKEN_BYTES = 32

# A fixed bcrypt hash of a random throwaway value, verified against on unknown
# emails so a login attempt costs the same whether or not the account exists
# (SEC-016: response time must not reveal account existence). Computed lazily so
# importing this module does not pay a bcrypt round at import time.
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(TOKEN_BYTES), bcrypt.gensalt()).decode(
            "utf-8"
        )
    return _DUMMY_HASH


def verify_password_timing_safe(password: str, password_hash: str | None) -> bool:
    """Always burn a bcrypt verification, even for unknown accounts.

    When ``password_hash`` is None (no such user) we verify against a precomputed
    dummy hash so the response time is indistinguishable from a wrong password on
    a real account. Returns the true match result (always False for the dummy).
    """
    if password_hash is None:
        verify_password(password, _dummy_hash())
        return False
    return verify_password(password, password_hash)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Raises ValueError on empty/too-long input."""
    if not password:
        raise ValueError("Password must not be empty")
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash. Never raises on mismatch."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """Generate a cryptographically random session token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 a bearer token for storage.

    Session and recovery tokens are stored only as this digest, so a database
    leak cannot be replayed as a live cookie (SEC-021). SHA-256 (not bcrypt) is
    correct here: the tokens are already 256-bit random, so brute-forcing the
    digest is infeasible and the lookup must stay fast and indexable.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(now: datetime | None = None) -> datetime:
    """Compute session expiry from the configured TTL.

    Aware datetimes throughout: ``sessions.expires_at`` is ``timestamptz``, so a
    naive value here would be interpreted in the database server's zone.
    """
    base = now or utc_now()
    return base + timedelta(hours=settings.session_ttl_hours)
