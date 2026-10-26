"""Shared API dependencies: current-user resolution and auth rate limiting."""

import ipaddress
import math
import time
from collections import defaultdict
from collections.abc import Generator, Mapping
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.core.database import get_db, settings
from app.core.telemetry import record_rate_limit_rejection
from app.models.user import User

SESSION_COOKIE = "session_token"

# In-memory per-client rate limiter for auth endpoints (single-process dev
# default; replace with Redis for multi-worker production).
_rate_buckets: defaultdict[str, list[float]] = defaultdict(list)
# Separate bucket for online move submissions (online-plan §6.1), keyed by
# user id — mirrors the auth limiter; same single-process caveat.
_move_buckets: defaultdict[int, list[float]] = defaultdict(list)
# Coach assistant asks (Phase 11), keyed by user id — an LLM/what-if question is
# more expensive than a page read, so it gets its own budget. Same caveat.
_assistant_buckets: defaultdict[int, list[float]] = defaultdict(list)
# Training attempts (Phase 12A, RL-002): every one writes a ledger row.
_training_buckets: defaultdict[int, list[float]] = defaultdict(list)
# Review generations (RL-001): weighted entries, not plain hits — a forced
# re-run costs 2 because it re-holds the warm engine while a plain POST that
# finds the cached review still costs the check it ran.
_review_buckets: defaultdict[int, list[tuple[float, int]]] = defaultdict(list)

REVIEW_WINDOW_S = 60.0 * 60.0


def _retry_after(seconds_left: float) -> dict[str, str]:
    """RL-004: every 429 names when the caller may return, not just "later"."""
    return {"Retry-After": str(max(1, math.ceil(seconds_left)))}


def _trusted_proxy_nets() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse `trusted_proxy_cidrs` once per call (a settings string, comma-
    separated; invalid entries are skipped rather than shutting the limiter).
    """
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for chunk in settings.trusted_proxy_cidrs.split(","):
        entry = chunk.strip()
        if not entry:
            continue
        try:
            nets.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            continue
    return nets


def client_ip(request: Request) -> str:
    """The address a per-client limiter should key on (RB-004, TD-021).

    Off by default, which is byte-for-byte the old behavior: the direct peer.
    With `TRUST_PROXY_HEADERS` on and the direct peer inside a trusted CIDR,
    walk `X-Forwarded-For` from the right and return the closest hop that is
    *not itself* a trusted proxy (nginx `real_ip_recursive` semantics). Each
    proxy appends the address it saw, so the rightmost non-proxy hop is the
    real client; the leftmost value is one a client can prepend and forge, so
    it is never trusted outright. With trust on but an untrusted peer, XFF is
    *ignored* — a direct client must never mint free limiter buckets. Values
    that are not parseable IPs fall back to the peer.
    """
    peer = request.client.host if request.client else "unknown"
    if not settings.trust_proxy_headers:
        return peer
    nets = _trusted_proxy_nets()
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not any(peer_addr in net for net in nets):
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    for token in reversed(forwarded.split(",")):
        candidate = token.strip()
        if not candidate:
            continue
        try:
            addr = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if any(addr in net for net in nets):
            continue  # an inner trusted hop; keep walking toward the client
        return candidate
    return peer


def rate_limit_auth(request: Request) -> None:
    """Allow N auth attempts per minute per client IP (SEC-012)."""
    now = time.monotonic()
    window_start = now - 60.0
    key = client_ip(request)
    hits = [t for t in _rate_buckets[key] if t > window_start]
    _rate_buckets[key] = hits
    if len(hits) >= settings.auth_rate_limit_per_minute:
        record_rate_limit_rejection("auth")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
            headers=_retry_after(hits[0] + 60.0 - now),
        )
    hits.append(now)


def reset_rate_limits() -> None:
    """Clear rate-limit state (used by tests)."""
    _rate_buckets.clear()
    _move_buckets.clear()
    _assistant_buckets.clear()
    _training_buckets.clear()
    _review_buckets.clear()


def same_origin_ok(headers: Mapping[str, str]) -> bool:
    """Return whether an Origin/Referer header value passes the allowlist.

    Shared by the HTTP dependency and the WebSocket handshake (CSWSRF).
    Requests without either header (curl, tests) pass, like `enforce_same_origin`.
    """
    origin = headers.get("origin")
    referer = headers.get("referer")
    if not origin and not referer:
        return True
    allowed = {o.strip().rstrip("/") for o in settings.cors_origins.split(",") if o.strip()}
    candidate = (origin or referer or "").rstrip("/")
    return candidate in allowed


def enforce_same_origin(request: Request) -> None:
    """Reject cross-origin state-changing requests (SEC-008, CSRF defense).

    Browsers attach `Origin` (or `Referer`) to cross-site POSTs; same-origin
    fetch/XHR from our frontend carries our own origin. Requests without
    either header (curl, tests, non-browser clients) are allowed through —
    they cannot be forged cross-site form/fetch submissions.
    """
    if not same_origin_ok(request.headers):
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


def check_move_rate(user_id: int) -> None:
    """Allow N move submissions per minute per user (online-plan §6.1).

    Shared by the REST dependency and the WebSocket dispatch so choosing a
    transport cannot bypass the limit.
    """
    now = time.monotonic()
    window_start = now - 60.0
    hits = [t for t in _move_buckets[user_id] if t > window_start]
    _move_buckets[user_id] = hits
    if len(hits) >= settings.move_rate_limit_per_minute:
        record_rate_limit_rejection("moves")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many moves. Please slow down.",
            headers=_retry_after(hits[0] + 60.0 - now),
        )
    hits.append(now)


def rate_limit_moves(current_user: Annotated[User, Depends(get_current_user)]) -> None:
    """REST dependency wrapper around :func:`check_move_rate`."""
    check_move_rate(current_user.id)


def check_assistant_rate(user_id: int) -> None:
    """Allow N coach-assistant asks per minute per user (Phase 11).

    A question can trigger a live engine pass and (when configured) an LLM call,
    so it is capped more tightly than ordinary reads. Mirrors :func:`check_move_rate`.
    """
    now = time.monotonic()
    window_start = now - 60.0
    hits = [t for t in _assistant_buckets[user_id] if t > window_start]
    _assistant_buckets[user_id] = hits
    if len(hits) >= settings.assistant_rate_limit_per_minute:
        record_rate_limit_rejection("assistant")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many questions. Please slow down.",
            headers=_retry_after(hits[0] + 60.0 - now),
        )
    hits.append(now)


def rate_limit_assistant(current_user: Annotated[User, Depends(get_current_user)]) -> None:
    """REST dependency wrapper around :func:`check_assistant_rate`."""
    check_assistant_rate(current_user.id)


def check_training_rate(user_id: int) -> None:
    """Allow N training attempts per minute per user (Phase 12A, RL-002).

    Every attempt grades and may write a ledger row, so it gets a ceiling —
    modest enough that real study never touches it. Mirrors :func:`check_move_rate`.
    """
    now = time.monotonic()
    window_start = now - 60.0
    hits = [t for t in _training_buckets[user_id] if t > window_start]
    _training_buckets[user_id] = hits
    if len(hits) >= settings.training_rate_limit_per_minute:
        record_rate_limit_rejection("training")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please slow down.",
            headers=_retry_after(hits[0] + 60.0 - now),
        )
    hits.append(now)


def rate_limit_training(current_user: Annotated[User, Depends(get_current_user)]) -> None:
    """REST dependency wrapper around :func:`check_training_rate`."""
    check_training_rate(current_user.id)


def check_review_rate(user_id: int, *, force: bool) -> None:
    """Review generation budget (Phase 12A, RL-001).

    A generation holds a warm engine for seconds of real CPU (TD-013), so it is
    the one write surface costed **per hour** instead of per minute — and a
    forced re-run pays double. The cached GET path never comes through here.
    """
    weight = 2 if force else 1
    now = time.monotonic()
    window_start = now - REVIEW_WINDOW_S
    entries = [(t, w) for t, w in _review_buckets[user_id] if t > window_start]
    _review_buckets[user_id] = entries
    if sum(w for _, w in entries) + weight > settings.review_rate_limit_per_hour:
        record_rate_limit_rejection("review")
        seconds_left = entries[0][0] + REVIEW_WINDOW_S - now if entries else REVIEW_WINDOW_S
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reviews this hour. Please try again later.",
            headers=_retry_after(seconds_left),
        )
    entries.append((now, weight))
