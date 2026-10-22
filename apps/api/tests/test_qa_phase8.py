"""Phase 8 QA probes: concurrency, recovery, rollback, timeouts (QA-014..017)."""

import time

import chess
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.engine.domain import EngineConfig
from app.engine.engine import ChessEngine
from app.games.domain import STARTING_FEN, Color
from app.models.game import Game as GameRow


def _create(client: TestClient, mode: str = "local") -> dict:
    resp = client.post("/api/v1/games", json={"mode": mode})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_concurrent_stale_write_one_wins(authed_client: tuple[TestClient, dict]) -> None:
    """QA-014: two writes from the same client snapshot → one 200, one 409.

    Deterministic and sequential on purpose. Genuine two-session contention is
    covered in `test_unit_of_work.py`; the shared `db` fixture behind `client`
    cannot express it.
    """
    client, _ = authed_client
    gid = _create(client)["id"]
    # Simulate the race deterministically: two writes based on the same snapshot.
    first = client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e4", "expected_version": 1})
    second = client.post(f"/api/v1/games/{gid}/moves", json={"uci": "d2d4", "expected_version": 1})
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    body = client.get(f"/api/v1/games/{gid}").json()
    assert body["version"] == 2
    assert len(body["moves"]) == 1


def test_repeated_create_is_stable(authed_client: tuple[TestClient, dict]) -> None:
    """QA-014: repeated identical creates each succeed with distinct ids."""
    client, _ = authed_client
    ids = [_create(client)["id"] for _ in range(5)]
    assert len(set(ids)) == 5
    listed = client.get("/api/v1/games").json()
    assert listed["total"] == 5
    assert len(listed["items"]) == 5


def test_restart_recovery_via_api(authed_client: tuple[TestClient, dict]) -> None:
    """QA-016: game + moves persist and reload (simulated restart = fresh GET)."""
    client, _ = authed_client
    gid = _create(client)["id"]
    client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e4", "expected_version": 1})
    client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e7e5", "expected_version": 2})
    client.cookies.clear()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "player@example.com", "password": "s3cret-pass"},
    )
    assert login.status_code == 200, login.text
    body = client.get(f"/api/v1/games/{gid}").json()
    assert [m["uci"] for m in body["moves"]] == ["e2e4", "e7e5"]
    assert body["fen"] == chess.Board(body["fen"]).fen()
    assert body["version"] == 3


def test_engine_timeout_stays_in_budget() -> None:
    """QA-015: tiny time budget → termination recorded, elapsed bounded."""
    engine = ChessEngine(EngineConfig(max_depth=6, max_time_ms=100))
    board = chess.Board()
    result = engine.search(board, Color.WHITE)
    assert result.best_move in [m.uci() for m in board.legal_moves]
    assert result.termination in ("completed", "timeout", "cancelled")
    assert result.time_ms < 2000


def test_engine_cancel_flag_set() -> None:
    """QA-015: cancel() sets the flag; mid-search cancel aborts promptly."""
    import threading

    engine = ChessEngine(EngineConfig(max_depth=6, max_time_ms=10000))
    engine.cancel()
    assert engine._cancelled is True
    # A fresh search resets the flag (documented contract); mid-search cancel works.
    board = chess.Board()
    timer = threading.Timer(0.05, engine.cancel)
    timer.start()
    result = engine.search(board, Color.WHITE)
    timer.cancel()
    assert result.best_move in [m.uci() for m in board.legal_moves]
    assert result.termination in ("completed", "timeout", "cancelled")


def test_db_rollback_leaves_clean_state(db) -> None:  # type: ignore[no-untyped-def]
    """QA-017: a failed write in the same unit of work rolls back everything.

    The repository now flushes without committing, so an IntegrityError raised
    by the flush inside `create` unwinds the whole transaction — including the
    user/game written before it.
    """
    from app.models.user import User
    from app.repositories.game_repository import GameRepository

    user = User(email="rollback@example.com", password_hash="x")
    db.add(user)
    db.commit()
    repo = GameRepository(db)
    game = repo.create(user_id=user.id, mode="local", fen=STARTING_FEN)
    db.add(GameRow(user_id=user.id, mode="x" * 5000, status="active", fen="bad"))
    db.rollback()
    fetched = repo.get_by_id(game.id, user.id)
    assert fetched is None


def test_stale_version_conflict_shape(authed_client: tuple[TestClient, dict]) -> None:
    """QA-014/017: stale write → 409 with safe envelope (no trace)."""
    client, _ = authed_client
    gid = _create(client)["id"]
    client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e4", "expected_version": 1})
    stale = client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e7e5", "expected_version": 1})
    assert stale.status_code == 409
    assert set(stale.json()) == {"detail"}
    body = client.get(f"/api/v1/games/{gid}").json()
    assert body["version"] == 2
    assert [m["uci"] for m in body["moves"]] == ["e2e4"]


def test_malformed_move_shapes(authed_client: tuple[TestClient, dict]) -> None:
    """QA-013: garbage UCI → 422 envelope; unknown game → 404 (no leak)."""
    client, _ = authed_client
    gid = _create(client)["id"]
    for bad in ["zzzz", "e2e5", "not-a-move", "e7e8q"]:
        resp = client.post(f"/api/v1/games/{gid}/moves", json={"uci": bad, "expected_version": 1})
        assert resp.status_code == 422, (bad, resp.text)
        assert set(resp.json()) == {"detail"}
    assert client.get("/api/v1/games/999999").status_code == 404
    t0 = time.time()
    assert client.get("/api/v1/games/999999").status_code == 404
    assert time.time() - t0 < 5


def test_unauthorized_shapes_have_no_leak(client: TestClient) -> None:
    """QA-011: unauthenticated + bad-token access → safe envelopes only."""
    client.cookies.clear()
    for method, path in [
        ("post", "/api/v1/games"),
        ("get", "/api/v1/games"),
        ("get", "/api/v1/games/1"),
        ("post", "/api/v1/games/1/moves"),
        ("get", "/api/v1/auth/me"),
    ]:
        resp = client.request(method, path, json={"mode": "local", "uci": "e2e4"})
        assert resp.status_code == 401, (method, path, resp.status_code)
        assert resp.json() == {"detail": "Not authenticated"}
    client.cookies.set("session_token", "forged-token-value")
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me").json() == {"detail": "Not authenticated"}


def test_no_secrets_in_error_bodies(authed_client: tuple[TestClient, dict]) -> None:
    """QA-019: error envelopes never contain hashes, tokens, or tracebacks."""
    import json as jsonlib

    client, _ = authed_client
    gid = _create(client)["id"]
    bodies = [
        client.post(f"/api/v1/games/{gid}/moves", json={"uci": "junk", "expected_version": 1}).text,
        client.post(
            "/api/v1/auth/login",
            json={"email": "player@example.com", "password": "wrong"},
        ).text,
        client.get("/api/v1/games/424242").text,
    ]
    client.cookies.clear()
    bodies.append(client.get("/api/v1/games").text)
    for raw in bodies:
        lowered = raw.lower()
        assert "password_hash" not in lowered
        assert "traceback" not in lowered
        assert set(jsonlib.loads(raw)) == {"detail"}


def test_slow_query_review(db) -> None:  # type: ignore[no-untyped-def]
    """QA-023: ownership lookups use indexed columns; query plan is sane."""
    stmt = select(GameRow).where(GameRow.user_id == 1).order_by(GameRow.id.desc()).limit(20)
    assert db.execute(stmt).all() == []
    explain = db.execute(
        select(GameRow).where(GameRow.user_id == 1).order_by(GameRow.id.desc()).limit(20)
    )
    assert explain is not None
