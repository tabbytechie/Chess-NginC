"""Single-use, purpose-scoped account-recovery tokens (SEC-013).

A token is a 32-byte URL-safe secret handed to the user (in an email link); the
database stores only an HMAC-SHA256 digest keyed by ``settings.secret_key``. The
same secret also gives ``secret_key`` its production job (ADR: reset-token
derivation). Tokens are consumed once, expire on a purpose-specific TTL, and are
never interchangeable between verification and reset.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.database import settings
from app.models.auth_token import AuthToken, TokenPurpose

# Raw secret bytes behind the URL-safe token: 256 bits of entropy.
TOKEN_BYTES = 32


def _ttl(purpose: TokenPurpose) -> timedelta:
    if purpose is TokenPurpose.PASSWORD_RESET:
        return timedelta(minutes=settings.password_reset_ttl_minutes)
    return timedelta(hours=settings.email_verification_ttl_hours)


def _derive(token: str) -> str:
    """Keyed digest stored at rest; recomputed identically on lookup."""
    return hmac.new(
        settings.secret_key.encode("utf-8"), token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def issue_token(db: Session, user_id: int, purpose: TokenPurpose) -> tuple[AuthToken, str]:
    """Create and persist a recovery token; return (row, plaintext_token).

    Any outstanding unconsumed tokens for the same purpose are retired first, so
    requesting a fresh link invalidates older ones. The caller commits nothing on
    the returned row beyond this function's own commit.
    """
    now = utc_now()
    for stale in db.execute(
        select(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose.value,
            AuthToken.consumed_at.is_(None),
        )
    ).scalars():
        stale.consumed_at = now
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    row = AuthToken(
        user_id=user_id,
        purpose=purpose.value,
        token_hash=_derive(raw),
        expires_at=now + _ttl(purpose),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def consume_token(db: Session, token: str, purpose: TokenPurpose) -> AuthToken | None:
    """Validate and consume a token, returning it (with `user_id`) or None.

    Rejects unknown, already-consumed, expired, or wrong-purpose tokens with the
    same None so callers cannot tell which — and never leaks validity timing.
    """
    if not token:
        return None
    row = db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == _derive(token),
            AuthToken.purpose == purpose.value,
            AuthToken.consumed_at.is_(None),
        )
    ).scalar_one_or_none()
    if row is None or row.expires_at <= utc_now():
        return None
    row.consumed_at = utc_now()
    db.commit()
    return row
