"""Authentication endpoints: register, login, logout, me, recovery (SEC-001..013)."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import (
    SESSION_COOKIE,
    enforce_same_origin,
    get_current_user,
    get_db_session,
    rate_limit_auth,
)
from app.auth import recovery
from app.auth import service as auth_service
from app.auth.security import MAX_PASSWORD_BYTES
from app.core.database import settings
from app.models.user import User

from .schemas import (
    EmailRequest,
    ErrorResponse,
    LoginRequest,
    RecoveryMessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
    VerifyEmailRequest,
)

router = APIRouter(tags=["auth"])

# Module-level dependency singletons (kept after imports; ruff E402 exempted
# since FastAPI requires these as Annotated metadata, not call-site Defaults).
_DbSession = Depends(get_db_session)  # noqa: E402
_SessionCookie = Cookie(alias=SESSION_COOKIE)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402


def _web_base_url(request: Request) -> str:
    """Public origin used to build clickable recovery links in emails."""
    configured = settings.public_web_base_url.strip()
    return configured or str(request.base_url).rstrip("/")


def _set_auth_cookies(response: Response, token: str) -> None:
    """Set the session cookie (SEC-007: HttpOnly + SameSite=Lax).

    CSRF defense (SEC-008) is SameSite=Lax plus the Origin/Referer check in
    `enforce_same_origin`, not a separate synchronizer token.
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, email_verified=user.email_verified)


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limit_auth), Depends(enforce_same_origin)],
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, _DbSession],
) -> UserResponse:
    """Register a new account, start a session, and mail a verification link."""
    if len(payload.password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is too long")
    try:
        user = auth_service.register(db, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    # Best-effort: a failed send must not fail registration (the user can resend).
    recovery.send_verification(db, user, _web_base_url(request))
    result = auth_service.login(db, payload.email, payload.password)
    _set_auth_cookies(response, result.token)
    return _to_user_response(user)


@router.post(
    "/auth/login",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limit_auth), Depends(enforce_same_origin)],
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, _DbSession],
) -> UserResponse:
    """Authenticate with email + password and start a session (SEC-004)."""
    try:
        result = auth_service.login(db, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from None
    _set_auth_cookies(response, result.token)
    return _to_user_response(result.user)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(enforce_same_origin)],
)
def logout(
    response: Response,
    db: Annotated[Session, _DbSession],
    session_token: Annotated[str | None, _SessionCookie] = None,
) -> None:
    """Revoke the current session; always clears cookies (SEC-005, idempotent)."""
    auth_service.logout(db, session_token or "")
    _clear_auth_cookies(response)


@router.get("/auth/me", response_model=UserResponse, responses={401: {"model": ErrorResponse}})
def me(current_user: Annotated[User, _CurrentUser]) -> UserResponse:
    """Return the currently authenticated user (SEC-006)."""
    return _to_user_response(current_user)


@router.post(
    "/auth/verify-email",
    response_model=RecoveryMessageResponse,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limit_auth), Depends(enforce_same_origin)],
)
def verify_email(
    payload: VerifyEmailRequest,
    db: Annotated[Session, _DbSession],
) -> RecoveryMessageResponse:
    """Confirm an email address with a verification token (SEC-013).

    The reply reflects token validity, not account existence, so it is safe to
    distinguish success from an invalid/expired token.
    """
    if not recovery.verify_email(db, payload.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link"
        )
    return RecoveryMessageResponse(detail="Email verified.")


@router.post(
    "/auth/resend-verification",
    response_model=RecoveryMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limit_auth), Depends(enforce_same_origin)],
)
def resend_verification(
    payload: EmailRequest,
    request: Request,
    db: Annotated[Session, _DbSession],
) -> RecoveryMessageResponse:
    """Re-send a verification link. The reply is identical for any email."""
    detail = recovery.request_verification_for_email(db, payload.email, _web_base_url(request))
    return RecoveryMessageResponse(detail=detail)


@router.post(
    "/auth/request-password-reset",
    response_model=RecoveryMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limit_auth), Depends(enforce_same_origin)],
)
def request_password_reset(
    payload: EmailRequest,
    request: Request,
    db: Annotated[Session, _DbSession],
) -> RecoveryMessageResponse:
    """Send a password-reset link. The reply never reveals if the email exists."""
    detail = recovery.request_password_reset(db, payload.email, _web_base_url(request))
    return RecoveryMessageResponse(detail=detail)


@router.post(
    "/auth/reset-password",
    response_model=RecoveryMessageResponse,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limit_auth), Depends(enforce_same_origin)],
)
def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[Session, _DbSession],
) -> RecoveryMessageResponse:
    """Set a new password with a valid reset token and revoke all sessions."""
    if recovery.reset_password(db, payload.token, payload.password) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link"
        )
    return RecoveryMessageResponse(detail="Password reset. Please log in again.")
