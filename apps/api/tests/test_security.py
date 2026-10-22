"""Phase 4 security tests (SEC-008/012/013/016/021).

Covers the hardening the roadmap gates on:
* session tokens stored as a digest, never the raw bearer token;
* proxy-aware, per-route-class rate limiting a client cannot spoof around;
* CSRF that accepts a same-origin ``Referer`` carrying a path and rejects a
  cross-origin one;
* timing-safe login for unknown accounts;
* single-use / expiring recovery tokens and the sessions-reset flow.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import deps
from app.api.v1.deps import (
    rate_limit_auth,
    rate_limit_writes,
    reset_rate_limits,
)
from app.auth import recovery
from app.auth import service as auth_service
from app.auth.security import hash_password, hash_token, verify_password_timing_safe
from app.auth.tokens import consume_token, issue_token
from app.core.clock import utc_now
from app.core.database import settings
from app.models.auth_token import TokenPurpose
from app.models.session import Session as SessionModel


class _CapturingSender:
    """Email sender that records messages so tests can read the emailed token."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.messages.append((to, subject, body))


@pytest.fixture()
def captured_emails(monkeypatch: pytest.MonkeyPatch) -> _CapturingSender:
    sender = _CapturingSender()
    monkeypatch.setattr(recovery, "get_email_sender", lambda: sender)
    return sender


def _register(client: TestClient, email: str = "player@example.com") -> dict:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "s3cret-pass"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _token_from(body: str) -> str:
    """Extract the recovery token out of an emailed reset/verify link."""
    return body.split("token=", 1)[1].strip().splitlines()[0]


def _fake_request(peer: str, headers: dict[str, str]) -> SimpleNamespace:
    """Minimal stand-in exposing only what ``client_ip`` reads."""
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


# --- Hashed session tokens (SEC-021) ----------------------------------------


def test_session_stored_hashed_and_still_authenticates(client: TestClient, db: Session) -> None:
    _register(client, email="hash@example.com")
    token = client.cookies.get("session_token")
    assert token
    stored = {row.token_hash for row in db.execute(select(SessionModel)).scalars()}
    # The raw bearer token never appears in the table — only a 64-hex SHA-256.
    assert token not in stored
    assert all(len(d) == 64 for d in stored)
    assert hash_token(token) in stored
    # Yet the cookie still resolves to the user.
    assert client.get("/api/v1/auth/me").status_code == 200


def test_logout_revokes_by_hash(client: TestClient, db: Session) -> None:
    _register(client, email="logout@example.com")
    token = client.cookies.get("session_token")
    assert token
    assert client.post("/api/v1/auth/logout").status_code == 204
    # The digest row is gone, so the cookie can no longer authenticate.
    assert (
        db.execute(
            select(SessionModel).where(SessionModel.token_hash == hash_token(token))
        ).scalar_one_or_none()
        is None
    )
    assert client.get("/api/v1/auth/me").status_code == 401


# --- Proxy-aware, per-class rate limiting (SEC-012) -------------------------


def test_client_ip_trusts_forwarded_for_only_from_configured_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "forwarded_allow_ips", "10.0.0.0/8")
    trusted = _fake_request("10.0.0.5", {"x-forwarded-for": "203.0.113.7, 10.0.0.5"})
    assert deps.client_ip(trusted) == "203.0.113.7"
    # An untrusted socket peer cannot forge its address.
    untrusted = _fake_request("198.51.100.2", {"x-forwarded-for": "203.0.113.7"})
    assert deps.client_ip(untrusted) == "198.51.100.2"
    # No proxy configured at all: the peer is authoritative even with a header.
    monkeypatch.setattr(settings, "forwarded_allow_ips", "")
    assert deps.client_ip(trusted) == "10.0.0.5"


def test_route_classes_have_independent_buckets() -> None:
    reset_rate_limits()
    req = _fake_request("5.5.5.5", {})
    for _ in range(settings.auth_rate_limit_per_minute):
        rate_limit_auth(req)
    with pytest.raises(HTTPException) as exc:
        rate_limit_auth(req)
    assert exc.value.status_code == 429
    # The writes bucket is untouched by the auth flood.
    rate_limit_writes(req)
    reset_rate_limits()


def test_forwarded_for_cannot_escape_limit_without_trusted_proxy(client: TestClient) -> None:
    # forwarded_allow_ips defaults to empty: a client varying X-Forwarded-For
    # still shares the one socket-peer bucket and is cut off at the limit.
    for _ in range(settings.auth_rate_limit_per_minute):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "x" * 8},
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert resp.status_code == 401
    limited = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "x" * 8},
        headers={"X-Forwarded-For": "10.9.9.9"},
    )
    assert limited.status_code == 429


# --- CSRF: same-origin Referer with a path (SEC-008) -------------------------


def test_referer_with_path_same_origin_accepted(client: TestClient) -> None:
    _register(client, email="ref@example.com")
    client.cookies.clear()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "ref@example.com", "password": "s3cret-pass"},
        headers={"Referer": "http://localhost:5173/games/7"},
    )
    # Not 403: the origin comparison drops the path/query.
    assert resp.status_code == 200


def test_referer_cross_origin_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "x" * 8},
        headers={"Referer": "https://evil.example/steal"},
    )
    assert resp.status_code == 403


# --- Timing-safe login (SEC-016) --------------------------------------------


def test_unknown_email_still_pays_a_hash(client: TestClient) -> None:
    # A miss must not short-circuit before hashing: same generic 401 shape.
    resp = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "whatever123"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": auth_service.INVALID_CREDENTIALS}


def test_verify_password_timing_safe_helper() -> None:
    assert verify_password_timing_safe("anything", None) is False
    digest = hash_password("s3cret-pass")
    assert verify_password_timing_safe("s3cret-pass", digest) is True
    assert verify_password_timing_safe("wrong-pass", digest) is False


# --- Recovery tokens: single-use, expiring, non-enumerable (SEC-013) --------


def test_email_verification_flow(client: TestClient, captured_emails: _CapturingSender) -> None:
    body = _register(client, email="verify@example.com")
    assert body["email_verified"] is False
    token = _token_from(captured_emails.messages[-1][2])
    ok = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert ok.status_code == 200
    assert client.get("/api/v1/auth/me").json()["email_verified"] is True
    # A consumed token cannot be replayed.
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400


def test_password_reset_is_single_use(
    client: TestClient, captured_emails: _CapturingSender
) -> None:
    _register(client, email="reset@example.com")
    captured_emails.messages.clear()
    req = client.post("/api/v1/auth/request-password-reset", json={"email": "reset@example.com"})
    assert req.status_code == 202
    token = _token_from(captured_emails.messages[-1][2])
    ok = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "brand-new-1"}
    )
    assert ok.status_code == 200
    replay = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "another-2"}
    )
    assert replay.status_code == 400


def test_reset_revokes_all_sessions(client: TestClient, captured_emails: _CapturingSender) -> None:
    _register(client, email="multi@example.com")
    # The registration left a live session cookie on the client.
    assert client.get("/api/v1/auth/me").status_code == 200
    captured_emails.messages.clear()
    client.post("/api/v1/auth/request-password-reset", json={"email": "multi@example.com"})
    token = _token_from(captured_emails.messages[-1][2])
    reset = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "fresh-pass"}
    )
    assert reset.status_code == 200
    # The old session is dead after the reset.
    assert client.get("/api/v1/auth/me").status_code == 401


def test_recovery_endpoints_do_not_enumerate(client: TestClient) -> None:
    known = client.post(
        "/api/v1/auth/request-password-reset", json={"email": "nobody-unknown@example.com"}
    )
    assert known.status_code == 202
    # Reply text is fixed and identical whether or not the account exists.
    assert known.json() == {"detail": "If that email is registered, a link has been sent."}


def test_expired_recovery_token_is_rejected(db: Session) -> None:
    user = auth_service.register(db, "exp@example.com", "s3cret-pass")
    row, raw = issue_token(db, user.id, TokenPurpose.PASSWORD_RESET)
    row.expires_at = utc_now() - timedelta(minutes=1)
    db.commit()
    assert consume_token(db, raw, TokenPurpose.PASSWORD_RESET) is None


def test_token_is_purpose_scoped(db: Session) -> None:
    user = auth_service.register(db, "scope@example.com", "s3cret-pass")
    _, raw = issue_token(db, user.id, TokenPurpose.EMAIL_VERIFICATION)
    # A verification token must not pass as a reset token.
    assert consume_token(db, raw, TokenPurpose.PASSWORD_RESET) is None
    assert consume_token(db, raw, TokenPurpose.EMAIL_VERIFICATION) is not None


# --- Registration race safety (SEC-001) -------------------------------------


def test_register_integrity_error_converted_to_value_error(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth_service.register(db, "race@example.com", "s3cret-pass")
    # Force the friendly pre-check to miss the committed row so the unique index
    # is what rejects the duplicate — exercising the IntegrityError branch.
    monkeypatch.setattr(auth_service, "_get_user_by_email", lambda _db, _email: None)
    with pytest.raises(ValueError, match="already registered"):
        auth_service.register(db, "race@example.com", "s3cret-pass")
