"""Shared API dependencies: current-user resolution and per-class rate limiting."""

import ipaddress
import time
from collections import defaultdict
from collections.abc import Callable, Generator
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.core.database import get_db, settings
from app.models.user import User

SESSION_COOKIE = "session_token"

# In-memory per-client rate limiter (single-process dev default; Redis is the
# documented production replacement for cross-process limiting — see TD register).
# Each route class gets its own bucket map so, e.g., a flood of auth retries
# cannot starve engine or write endpoints sharing the same client.
_rate_buckets: dict[str, defaultdict[str, list[float]]] = {
    "auth": defaultdict(list),
    "engine": defaultdict(list),
    "writes": defaultdict(list),
}


def _is_trusted_proxy(host: str) -> bool:
    """True when the socket peer is a proxy we are allowed to trust headers from."""
    spec = settings.forwarded_allow_ips.strip()
    if not spec:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    for token in (t.strip() for t in spec.split(",")):
        if not token:
            continue
        if token == "*":
            return True
        try:
            if addr in ipaddress.ip_network(token, strict=False):
                return True
        except ValueError:
            if token == host:
                return True
    return False


def client_ip(request: Request) -> str:
    """Resolve the real client address, trusting `X-Forwarded-For` only from a
    configured proxy (SEC-012). With no `forwarded_allow_ips`, the socket peer is
    authoritative — so a client cannot spoof its own rate-limit bucket."""
    peer = request.client.host if request.client else "unknown"
    if _is_trusted_proxy(peer):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or peer
    return peer


def _make_limiter(route_class: str, limit: Callable[[], int]) -> Callable[[Request], None]:
    """Build a dependency enforcing N requests/minute per client for one class."""
    buckets = _rate_buckets[route_class]

    def dependency(request: Request) -> None:
        now = time.monotonic()
        window_start = now - 60.0
        key = client_ip(request)
        hits = [t for t in buckets[key] if t > window_start]
        buckets[key] = hits
        if len(hits) >= limit():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please try again later.",
            )
        hits.append(now)

    return dependency


rate_limit_auth = _make_limiter("auth", lambda: settings.auth_rate_limit_per_minute)
rate_limit_engine = _make_limiter("engine", lambda: settings.engine_rate_limit_per_minute)
rate_limit_writes = _make_limiter("writes", lambda: settings.write_rate_limit_per_minute)


def reset_rate_limits() -> None:
    """Clear all rate-limit state (used by tests)."""
    for buckets in _rate_buckets.values():
        buckets.clear()


def _origin_tuple(url: str) -> str:
    """Reduce a full URL to its `scheme://netloc`, dropping path and query."""
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return url.rstrip("/")
    return f"{parts.scheme}://{parts.netloc}"


def enforce_same_origin(request: Request) -> None:
    """Reject cross-origin state-changing requests (SEC-008, CSRF defense).

    Browsers attach `Origin` (or `Referer`) to cross-site POSTs; same-origin
    fetch/XHR from our frontend carries our own origin. Requests without
    either header (curl, tests, non-browser clients) are allowed through —
    they cannot be forged cross-site form/fetch submissions.

    A legit `Referer: http://localhost:5173/games/7` carries a path, so the
    comparison is on `scheme://netloc`, not the whole URL string.
    """
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if not origin and not referer:
        return
    allowed = {_origin_tuple(o) for o in settings.cors_origins.split(",") if o.strip()}
    candidate = origin or referer
    if candidate is None:  # pragma: no cover - guarded by the check above
        return
    if _origin_tuple(candidate) not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin request forbidden",
        )


def get_db_session() -> Generator[Session, None, None]:
    """Yield a DB session (thin alias so routes depend on the api layer)."""
    yield from get_db()


# Module-level singletons for Annotated dependency metadata (E402 exempted).
# NOTE: FastAPI forbids defaults inside Annotated Cookie/Depends; the `= None`
# defaults live on the parameter declarations below.
_DbSession = Depends(get_db_session)  # noqa: E402
_SessionCookie = Cookie(alias=SESSION_COOKIE)  # noqa: E402


def get_current_user(
    session_token: Annotated[str | None, _SessionCookie] = None,
    db: Annotated[Session, _DbSession] = None,  # type: ignore[assignment]
) -> User:
    """Resolve the session cookie to a user or raise 401 (SEC-020)."""
    assert db is not None  # guaranteed by FastAPI dependency injection
    user = auth_service.authenticate(db, session_token or "")
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user
