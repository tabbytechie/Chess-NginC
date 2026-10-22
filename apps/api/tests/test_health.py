"""Tests for the health and readiness endpoints (REL-007)."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.v1 import health
from app.core.database import settings
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_service_name() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "chess-engine-api"


def test_ready_returns_200_when_database_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "_database_up", lambda: True)
    resp = client.get("/api/v1/ready")
    # Engine default backend is the in-process custom engine.
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "up", "engine": "builtin"}


def test_ready_returns_503_when_database_down(monkeypatch: pytest.MonkeyPatch) -> None:
    # A load balancer must be able to act on this, so DB failure is a real 503.
    monkeypatch.setattr(health, "_database_up", lambda: False)
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "not-ready"
    assert resp.json()["database"] == "down"


def test_ready_reports_engine_degraded_without_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "_database_up", lambda: True)
    monkeypatch.setattr(settings, "engine_backend", "stockfish_remote")
    monkeypatch.setattr(settings, "engine_base_url", "http://engine:8050")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise httpx.ConnectError("sidecar down")

    monkeypatch.setattr(httpx, "get", _boom)
    resp = client.get("/api/v1/ready")
    # Unreachable sidecar degrades the opponent but the site stays ready.
    assert resp.status_code == 200
    assert resp.json()["engine"] == "degraded"


def test_ready_reports_engine_up_when_sidecar_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "_database_up", lambda: True)
    monkeypatch.setattr(settings, "engine_backend", "stockfish_remote")

    class _Ok:
        status_code = 200

    monkeypatch.setattr(httpx, "get", lambda *_a, **_k: _Ok())
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    assert resp.json()["engine"] == "up"


def test_request_id_is_echoed_and_respected() -> None:
    # A minted id is returned for requests that carry none (REL-008).
    resp = client.get("/api/v1/health")
    assert resp.headers.get("X-Request-ID")
    # An inbound id from a trusted proxy is passed through unchanged.
    inbound = client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert inbound.headers["X-Request-ID"] == "abc123"
