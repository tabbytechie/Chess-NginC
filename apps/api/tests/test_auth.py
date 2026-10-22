"""Auth tests: registration, login, sessions, cookies, rate limits (SEC-001..021)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_token
from app.auth.validators import normalize_email
from app.core.clock import utc_now
from app.models.session import Session as SessionModel


def _register(
    client: TestClient, email: str = "Ada@Example.COM ", password: str = "s3cret-pass"
) -> dict:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_register_normalizes_email_and_sets_cookies(client: TestClient) -> None:
    body = _register(client)
    assert body["email"] == "ada@example.com"
    assert "id" in body
    assert "password_hash" not in body
    # Secure session cookie: HttpOnly + SameSite=Lax (SEC-007)
    session_cookie = client.cookies.get("session_token")
    assert session_cookie
    raw = client.post("/api/v1/auth/register", json={"email": "x@y.zz", "password": "x"})
    assert raw.status_code == 400  # short password rejected


def test_register_duplicate_and_invalid(client: TestClient) -> None:
    _register(client, email="dup@example.com")
    dup = client.post(
        "/api/v1/auth/register",
        json={"email": "DUP@example.com", "password": "s3cret-pass"},
    )
    assert dup.status_code == 400
    bad = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "s3cret-pass"},
    )
    assert bad.status_code == 400


def test_login_me_logout_flow(client: TestClient) -> None:
    _register(client, email="flow@example.com")
    client.cookies.clear()
    # Generic error shape on bad credentials (SEC-016: no account enumeration)
    bad = client.post(
        "/api/v1/auth/login", json={"email": "flow@example.com", "password": "wrong-pass"}
    )
    assert bad.status_code == 401
    assert bad.json() == {"detail": "Invalid email or password"}
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "s3cret-pass"}
    )
    assert unknown.status_code == 401
    assert unknown.json() == bad.json()

    ok = client.post(
        "/api/v1/auth/login", json={"email": "flow@example.com", "password": "s3cret-pass"}
    )
    assert ok.status_code == 200
    assert ok.json()["email"] == "flow@example.com"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "flow@example.com"

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_unauthenticated_is_401(client: TestClient) -> None:
    client.cookies.clear()
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_cross_origin_post_forbidden(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "x" * 8},
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 403


def test_same_origin_post_allowed(client: TestClient) -> None:
    _register(client, email="origin@example.com")
    client.cookies.clear()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "origin@example.com", "password": "s3cret-pass"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200


def test_expired_session_rejected(client: TestClient, db: Session) -> None:
    _register(client, email="exp@example.com")
    token = client.cookies.get("session_token")
    assert token
    # The DB stores a digest, never the raw token (SEC-021): look it up by hash.
    stmt = select(SessionModel).where(SessionModel.token_hash == hash_token(token))
    sess = db.execute(stmt).scalar_one()
    sess.expires_at = utc_now() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_auth_rate_limit(client: TestClient) -> None:
    for _ in range(10):
        resp = client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x" * 8}
        )
        assert resp.status_code == 401
    limited = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x" * 8}
    )
    assert limited.status_code == 429


def test_normalize_email_unit() -> None:
    assert normalize_email("  Ada@Example.COM ") == "ada@example.com"
    with pytest.raises(ValueError):
        normalize_email("not-an-email")
