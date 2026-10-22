"""Account recovery orchestration: verification and password reset (SEC-013).

Ties the token store, the email sender, and user state together. Every public
function is written so the route layer can return a uniform response regardless
of whether the target account exists — these flows must never enumerate emails.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.auth.email import get_email_sender
from app.auth.tokens import consume_token, issue_token
from app.auth.validators import normalize_email
from app.core.clock import utc_now
from app.models.auth_token import TokenPurpose
from app.models.user import User

# Fixed, non-committal copy so a request for a known or unknown email reads the
# same to the caller.
_GENERIC_SENT = "If that email is registered, a link has been sent."


def _verification_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/verify-email?token={token}"


def _reset_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/reset-password?token={token}"


def _user_by_email(db: Session, email: str) -> User | None:
    try:
        normalized = normalize_email(email)
    except ValueError:
        return None
    return db.execute(select(User).where(User.email == normalized)).scalar_one_or_none()


def send_verification(db: Session, user: User, base_url: str) -> str:
    """Issue a verification token and mail its link. Returns the plaintext token."""
    _, raw = issue_token(db, user.id, TokenPurpose.EMAIL_VERIFICATION)
    link = _verification_link(base_url, raw)
    get_email_sender().send(
        user.email,
        "Confirm your Chess NginC email",
        f"Welcome! Confirm your email to activate account recovery:\n\n{link}\n",
    )
    return raw


def request_verification_for_email(db: Session, email: str, base_url: str) -> str:
    """Send a verification link if the account exists; always the same reply."""
    user = _user_by_email(db, email)
    if user is not None and not user.email_verified:
        send_verification(db, user, base_url)
    return _GENERIC_SENT


def verify_email(db: Session, token: str) -> bool:
    """Consume an email-verification token and mark the user verified."""
    row = consume_token(db, token, TokenPurpose.EMAIL_VERIFICATION)
    if row is None:
        return False
    user = db.get(User, row.user_id)
    if user is None:
        return False
    if not user.email_verified:
        user.email_verified = True
        user.verified_at = utc_now()
        db.commit()
    return True


def request_password_reset(db: Session, email: str, base_url: str) -> str:
    """Send a reset link if the account exists; the reply never varies."""
    user = _user_by_email(db, email)
    if user is not None:
        _, raw = issue_token(db, user.id, TokenPurpose.PASSWORD_RESET)
        link = _reset_link(base_url, raw)
        get_email_sender().send(
            user.email,
            "Reset your Chess NginC password",
            f"Use this link to reset your password:\n\n{link}\n"
            "If you did not request this, you can ignore it.",
        )
    return _GENERIC_SENT


def reset_password(db: Session, token: str, new_password: str) -> datetime | None:
    """Reset a password with a valid token; revokes every session for the user.

    Returns the reset timestamp on success, or None for an invalid/expired token
    or a policy-violating new password. On success all outstanding sessions are
    dropped so a stolen cookie dies with the old password.
    """
    row = consume_token(db, token, TokenPurpose.PASSWORD_RESET)
    if row is None:
        return None
    user = db.get(User, row.user_id)
    if user is None:
        return None
    try:
        auth_service.set_password(user, new_password)
    except ValueError:
        return None
    db.commit()
    auth_service.revoke_all_sessions(db, user.id)
    return utc_now()
