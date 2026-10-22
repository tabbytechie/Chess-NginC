"""Shared test fixtures: live-Postgres DB session and authed API clients.

The database URL, the safety guard, and the engine all live in :mod:`tests.db`
so no fixture can accidentally bind to the app's production/dev engine.
"""

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (register tables on Base.metadata)
from app.api.v1.deps import get_db_session, reset_rate_limits
from app.core.database import Base
from app.main import app
from app.models.session import Session as SessionModel
from tests.db import TestingSession, engine, new_session


@pytest.fixture()
def db() -> Session:
    """Yield a DB session with a fresh schema per test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def raw_session() -> Session:
    """An independent session on the test DB, outside the per-test `db` one.

    Concurrency tests need separate transactions that really are separate, which
    a single shared session cannot provide.
    """
    session = new_session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db: Session) -> TestClient:
    """Yield a TestClient bound to the fixture DB session."""
    reset_rate_limits()

    def override_db() -> Session:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _wipe(db: Session) -> None:
    """Wipe domain tables in FK-safe order (children first; skip if absent).

    The db_session fixture in test_game_repository.py manages its own schema
    lifecycle, so this autouse wipe may run before tables exist — tolerate
    missing tables.
    """
    from sqlalchemy.exc import ProgrammingError

    from app.models.engine_run import EngineRun
    from app.models.game import Game
    from app.models.game_move import GameMove

    try:
        db.query(EngineRun).delete()
        db.query(GameMove).delete()
        db.query(Game).delete()
        db.query(SessionModel).delete()
        db.execute(sqlalchemy.text("DELETE FROM users"))
        db.commit()
    except ProgrammingError:
        db.rollback()


@pytest.fixture(autouse=True)
def _clean_tables(db: Session) -> None:
    """Wipe tables before/after each test."""
    _wipe(db)
    yield
    _wipe(db)


@pytest.fixture()
def authed_client(client: TestClient) -> tuple[TestClient, dict]:
    """Register a user and return (client, user body) with session cookie set."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "player@example.com", "password": "s3cret-pass"},
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()


@pytest.fixture()
def other_client(db: Session) -> TestClient:
    """A second independent client (separate user) for cross-account tests."""
    reset_rate_limits()

    def override_db() -> Session:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_db
    other = TestClient(app)
    try:
        resp = other.post(
            "/api/v1/auth/register",
            json={"email": "opponent@example.com", "password": "s3cret-pass"},
        )
        assert resp.status_code == 201, resp.text
        yield other
    finally:
        app.dependency_overrides.clear()
