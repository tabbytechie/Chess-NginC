"""Auth service: registration, login, session validation, logout (SEC-001..006)."""

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import (
    generate_session_token,
    hash_password,
    hash_token,
    session_expiry,
    verify_password_timing_safe,
)
from app.auth.validators import normalize_email, validate_password
from app.core.clock import utc_now
from app.models.session import Session as SessionModel
from app.models.user import User

# Generic message returned for both unknown-email and wrong-password logins
# so callers cannot enumerate registered accounts (SEC-016).
INVALID_CREDENTIALS = "Invalid email or password"


@dataclass(frozen=True)
class AuthResult:
    """Authenticated user plus the session token issued for them."""

    user: User
    token: str


def _get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def register(db: Session, email: str, password: str) -> User:
    """Create a new user. Raises ValueError on invalid input or duplicate email.

    The email check is a friendly pre-empt, not the authority: the unique index
    on `users.email` is. A concurrent insert that slips past the check is caught
    as an `IntegrityError` and reported identically, so the race cannot 500.
    """
    normalized = normalize_email(email)
    validate_password(password)
    if _get_user_by_email(db, normalized) is not None:
        raise ValueError("Email is already registered")
    user = User(email=normalized, password_hash=hash_password(password), email_verified=False)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Email is already registered") from None
    db.refresh(user)
    return user


def login(db: Session, email: str, password: str) -> AuthResult:
    """Authenticate and issue a session token. Raises ValueError on failure.

    Unknown emails still pay a bcrypt verification against a dummy hash, so the
    response time does not disclose whether the account exists (SEC-016).
    """
    try:
        normalized = normalize_email(email)
    except ValueError:
        raise ValueError(INVALID_CREDENTIALS) from None
    user = _get_user_by_email(db, normalized)
    password_hash = user.password_hash if user is not None else None
    if not verify_password_timing_safe(password, password_hash) or user is None:
        raise ValueError(INVALID_CREDENTIALS)
    token = generate_session_token()
    db.add(
        SessionModel(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=session_expiry(),
        )
    )
    db.commit()
    return AuthResult(user=user, token=token)


def authenticate(db: Session, token: str) -> User | None:
    """Resolve a session token to its user, or None if unknown/expired (SEC-021).

    The token is hashed before lookup: the database only ever holds digests, so
    a stolen row cannot be replayed as a live cookie.
    """
    if not token:
        return None
    stmt = select(SessionModel).where(SessionModel.token_hash == hash_token(token))
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        return None
    if session.expires_at <= utc_now():
        db.delete(session)
        db.commit()
        return None
    return db.get(User, session.user_id)


def logout(db: Session, token: str) -> bool:
    """Revoke a session token. Returns True if a session was revoked (SEC-005)."""
    if not token:
        return False
    stmt = select(SessionModel).where(SessionModel.token_hash == hash_token(token))
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        return False
    db.delete(session)
    db.commit()
    return True


def revoke_all_sessions(db: Session, user_id: int) -> int:
    """Drop every outstanding session for a user (SEC-013: after a password reset).

    Returns the number revoked; the caller commits.
    """
    result = db.execute(delete(SessionModel).where(SessionModel.user_id == user_id))
    db.commit()
    # `rowcount` is a Cursor-family attribute; the base Result type hides it.
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def set_password(user: User, password: str) -> None:
    """Overwrite the password hash after validating policy; does not commit."""
    validate_password(password)
    user.password_hash = hash_password(password)


def prune_expired_sessions(db: Session) -> int:
    """Delete sessions whose expiry has passed; returns rows removed (SEC-021)."""
    result = db.execute(delete(SessionModel).where(SessionModel.expires_at <= utc_now()))
    db.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
