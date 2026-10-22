"""Unit-of-work guarantees: atomic move writes under real concurrency (DB-008/009).

Everything here uses *separate sessions on separate threads*. The `client`
fixture deliberately shares one session across requests, which is convenient but
cannot expose a lost update — that is the whole defect this suite exists to
catch.
"""

import threading
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db_session
from app.games import service
from app.games.domain import STARTING_FEN
from app.games.rules import ChessRules
from app.main import app
from app.models.game import Game as GameRow
from app.models.game_move import GameMove as GameMoveRow
from app.models.user import User
from tests.db import TestingSession, new_session


def _fen_after(uci: str) -> str:
    """The position a single ply from the start produces.

    Derived through the rules adapter rather than transcribed by hand: a typed
    FEN here would drift exactly like the bug this file is testing.
    """
    return ChessRules.from_moves([uci], STARTING_FEN).fen


@pytest.fixture()
def raced_game(db: Session) -> tuple[int, int]:
    """A committed user + game, returned as (game_id, user_id)."""
    return _committed_game(db, "race@example.com")


def _committed_game(db: Session, email: str) -> tuple[int, int]:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, password_hash="hash")
        db.add(user)
        db.commit()
    game = service.create_game(db, user.id, "local")
    return game.game.id, user.id


def _submit(
    game_id: int,
    user_id: int,
    uci: str,
    version: int,
    ready: threading.Barrier,
    results: dict[str, object],
    key: str,
) -> None:
    """One move attempt on its own session and thread.

    Both threads read the game and then wait at ``ready`` before writing, so each
    is guaranteed to hold the same pre-write snapshot. The version that used to
    be lost between "read" and "write" is now checked inside the write itself.
    """
    session = new_session()
    try:
        results[f"{key}_read_version"] = service.get_game(session, game_id, user_id).game.version
        ready.wait(5)
        results[key] = service.submit_move(session, game_id, user_id, uci, version)
    except BaseException as exc:  # noqa: BLE001 - recorded and asserted by the test
        results[f"{key}_error"] = exc
    finally:
        session.close()


def test_two_threads_same_game_exactly_one_wins(raced_game: tuple[int, int]) -> None:
    """Real contention: one winner, one StaleVersionError, no orphan ply."""
    game_id, user_id = raced_game
    moves = ("e2e4", "d2d4")
    ready = threading.Barrier(2)
    results: dict[str, object] = {}
    threads = [
        threading.Thread(target=_submit, args=(game_id, user_id, uci, 1, ready, results, key))
        for key, uci in zip(("mover0", "mover1"), moves, strict=True)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)

    assert not any(thread.is_alive() for thread in threads), "a write deadlocked"
    # Both sessions genuinely read the same stale snapshot before writing.
    assert results["mover0_read_version"] == results["mover1_read_version"] == 1

    winners = [key for key in ("mover0", "mover1") if key in results]
    errors = [results[f"{key}_error"] for key in ("mover0", "mover1") if f"{key}_error" in results]
    assert len(winners) == 1, f"expected exactly one winner, got {winners}"
    assert len(errors) == 1 and isinstance(errors[0], service.StaleVersionError), errors

    session = new_session()
    try:
        game = session.get(GameRow, game_id)
        assert game is not None
        assert game.version == 2, "the loser must not bump the version either"
        plies = (
            session.execute(
                select(GameMoveRow)
                .where(GameMoveRow.game_id == game_id)
                .order_by(GameMoveRow.move_number)
            )
            .scalars()
            .all()
        )
        # The losing move row must not survive: exactly one ply, and the stored
        # FEN is the position that single ply produces.
        assert len(plies) == 1
        assert plies[0].uci in moves
        assert game.fen == _fen_after(plies[0].uci)
        assert ChessRules.from_moves([plies[0].uci], STARTING_FEN).fen == game.fen
    finally:
        session.close()


def _move_count(session: Session, game_id: int) -> int:
    stmt = select(func.count()).select_from(GameMoveRow).where(GameMoveRow.game_id == game_id)
    return int(session.execute(stmt).scalar_one())


def test_failed_move_leaves_history_and_version_consistent(raced_game: tuple[int, int]) -> None:
    """Invariant: after any failed move, count(moves) and version stay in step."""
    game_id, user_id = raced_game
    session = new_session()

    def stored_plies() -> int:
        return _move_count(session, game_id)

    try:
        with pytest.raises(service.IllegalMoveRequestError):
            service.submit_move(session, game_id, user_id, "e2e5", 1)
        game = service.get_game(session, game_id, user_id).game
        assert game.version == 1
        assert game.fen == STARTING_FEN
        assert stored_plies() == 0

        with pytest.raises(service.StaleVersionError):
            service.submit_move(session, game_id, user_id, "e2e4", 99)
        assert service.get_game(session, game_id, user_id).game.version == 1
        assert stored_plies() == 0
    finally:
        session.close()


def test_move_number_survives_a_rejected_second_ply(raced_game: tuple[int, int]) -> None:
    """A rolled-back ply must not consume a move number from the history."""
    game_id, user_id = raced_game
    session = new_session()
    try:
        service.submit_move(session, game_id, user_id, "e2e4", 1)
        with pytest.raises(service.StaleVersionError):
            service.submit_move(session, game_id, user_id, "e7e5", 1)  # stale snapshot
        detail = service.get_game(session, game_id, user_id)
        assert [m.move_number for m in detail.moves] == [1]
        detail = service.submit_move(session, game_id, user_id, "e7e5", detail.game.version)
        assert [m.move_number for m in detail.moves] == [1, 2]
    finally:
        session.close()


def test_rules_replay_reproduces_the_stored_position(raced_game: tuple[int, int]) -> None:
    """Replaying the persisted history is exact, so status checks are honest."""
    game_id, user_id = raced_game
    session = new_session()
    try:
        version = 1
        detail = None
        for uci in ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]:
            detail = service.submit_move(session, game_id, user_id, uci, version)
            version = detail.game.version
        assert detail is not None
        rules = ChessRules.from_moves([m.uci for m in detail.moves], STARTING_FEN)
        assert rules.fen == detail.game.fen
        assert rules.is_check() is False
    finally:
        session.close()


# ------------------------------------------------------------- over HTTP


def test_http_concurrent_moves_one_200_one_409(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    """The assessment's lost-update reproduction, over HTTP, on two sessions.

    Before the conditional update this produced version 2 with one FEN lost and
    two move rows for the same ply. It must now produce 200 + 409 and one ply.

    Each request gets its **own** session: the shared `client` fixture hands every
    request the same one, so requests over it are really a single transaction and
    can never hit row-level contention at all.
    """
    game_id, _ = _committed_game(  # same owner as the authed session's cookie
        db,
        "player@example.com",
    )
    moves = ("e2e4", "g1f3")
    statuses: dict[str, int] = {}
    bodies: dict[str, dict] = {}
    lock = threading.Lock()
    ready = threading.Barrier(2)

    def per_request_session() -> Generator[Session, None, None]:
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    def play(uci: str) -> None:
        ready.wait(5)
        resp = authed_client[0].post(
            f"/api/v1/games/{game_id}/moves",
            json={"uci": uci, "expected_version": 1},
        )
        with lock:
            statuses[uci] = resp.status_code
            bodies[uci] = resp.json()

    app.dependency_overrides[get_db_session] = per_request_session
    try:
        threads = [threading.Thread(target=play, args=(uci,)) for uci in moves]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert sorted(statuses.values()) == [200, 409], statuses
    # The winner is read out of the responses, not guessed from the order the
    # threads happened to record them in.
    winners = [uci for uci in moves if statuses[uci] == 200]
    assert len(winners) == 1
    winner = winners[0]
    assert bodies[winner]["fen"] == _fen_after(winner)
    assert bodies[winner]["version"] == 2
    assert len(bodies[winner]["moves"]) == 1

    session = new_session()
    try:
        game = session.get(GameRow, game_id)
        assert game is not None
        assert game.version == 2, "the loser must not bump the version either"
        assert _move_count(session, game_id) == 1, "the loser must not leave a move row"
        assert game.fen == bodies[winner]["fen"]
    finally:
        session.close()
