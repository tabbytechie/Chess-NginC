"""Tests for GameRepository: ownership, conditional state writes, flush-only semantics."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.games.domain import STARTING_FEN
from app.models.game import Game
from app.models.game_move import GameMove
from app.models.user import User
from app.repositories.game_repository import GameRepository
from tests.db import engine, new_session

AFTER_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


@pytest.fixture
def db_session() -> tuple[Session, int, int]:
    """Create a fresh database session for each test.

    Uses the *test* engine: `app.core.database.engine` would point at whatever
    database the developer has configured, and this fixture drops every table.
    """
    Base.metadata.create_all(bind=engine)
    session = new_session()
    try:
        # Create test users
        user1 = User(email="test1@example.com", password_hash="hashed1")
        user2 = User(email="test2@example.com", password_hash="hashed2")
        session.add(user1)
        session.add(user2)
        session.commit()
        session.refresh(user1)
        session.refresh(user2)
        yield session, user1.id, user2.id
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


def _create_game(repo: GameRepository, user_id: int) -> Game:
    return repo.create(user_id=user_id, mode="local", fen=STARTING_FEN)


def test_create_game(db_session: tuple[Session, int, int]) -> None:
    session, user1_id, _ = db_session
    game = _create_game(GameRepository(session), user1_id)
    assert game.id is not None
    assert game.user_id == user1_id
    assert game.mode == "local"
    assert game.status == "active"
    assert game.version == 1


def test_create_does_not_commit(db_session: tuple[Session, int, int]) -> None:
    """The repository flushes; the unit of work belongs to the service layer."""
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    session.rollback()
    assert repo.get_by_id(game.id, user_id=user1_id) is None


def test_get_by_id_ownership_enforced(db_session: tuple[Session, int, int]) -> None:
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)

    # Owner can access
    assert repo.get_by_id(game.id, user_id=user1_id) is not None

    # Different user cannot access
    assert repo.get_by_id(game.id, user_id=user2_id) is None


def test_apply_state_bumps_version(db_session: tuple[Session, int, int]) -> None:
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)

    assert repo.apply_state(game, fen=AFTER_FEN, status="active", expected_version=1) == 1
    session.commit()
    session.expire(game)
    assert game.version == 2
    assert game.fen == AFTER_FEN


def test_apply_state_rejects_stale_version(db_session: tuple[Session, int, int]) -> None:
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    session.refresh(game)

    # Second writer with the same snapshot touches zero rows (DB-008).
    assert repo.apply_state(game, fen=AFTER_FEN, status="active", expected_version=1) == 1
    assert repo.apply_state(game, fen=STARTING_FEN, status="active", expected_version=1) == 0


def test_apply_state_rejects_other_owner(db_session: tuple[Session, int, int]) -> None:
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    # A caller that hand-assembled a row with someone else's ownership cannot
    # write: the UPDATE's WHERE clause carries user_id, so it matches nothing.
    forged = Game(id=game.id, user_id=user2_id)
    assert repo.apply_state(forged, fen=AFTER_FEN, status="active", expected_version=1) == 0


def test_mark_finished_is_single_shot(db_session: tuple[Session, int, int]) -> None:
    """Two simultaneous resignations cannot both take effect."""
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)

    assert repo.mark_finished(game, "resigned") == 1
    assert repo.mark_finished(game, "resigned") == 0
    session.refresh(game)
    assert game.status == "resigned"
    assert game.version == 2


def test_add_move_and_count(db_session: tuple[Session, int, int]) -> None:
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)

    assert repo.count_moves(game.id) == 0
    move = repo.add_move(game, uci="e2e4", san="e4", move_number=1)
    assert move.uci == "e2e4"
    assert repo.count_moves(game.id) == 1


def test_duplicate_move_number_is_rejected(db_session: tuple[Session, int, int]) -> None:
    """UNIQUE (game_id, move_number): the numbering race has a database backstop."""
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    repo.add_move(game, uci="e2e4", san="e4", move_number=1)
    with pytest.raises(IntegrityError):
        repo.add_move(game, uci="e7e5", san="e5", move_number=1)
    session.rollback()


def test_get_moves_ownership_enforced(db_session: tuple[Session, int, int]) -> None:
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    repo.add_move(game, uci="e2e4", san="e4", move_number=1)

    # Owner can get moves
    assert len(repo.get_moves(game.id, user_id=user1_id)) == 1

    # Different user cannot get moves
    assert repo.get_moves(game.id, user_id=user2_id) == []


def test_delete_move_removes_the_row(db_session: tuple[Session, int, int]) -> None:
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    move = repo.add_move(game, uci="e2e4", san="e4", move_number=1)
    repo.delete_move(move)
    session.commit()
    assert repo.count_moves(game.id) == 0


def test_move_row_rolls_back_with_a_rejected_state(db_session: tuple[Session, int, int]) -> None:
    """The orphan-move defect: a rejected write must not leave a move behind."""
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    session.commit()

    repo.add_move(game, uci="e2e4", san="e4", move_number=1)
    applied = repo.apply_state(game, fen=AFTER_FEN, status="active", expected_version=99)
    session.rollback()

    assert applied == 0
    assert repo.count_moves(game.id) == 0
    fresh = repo.get_by_id(game.id, user_id=user1_id)
    assert fresh is not None
    assert fresh.version == 1
    assert fresh.fen == STARTING_FEN


def test_deleting_a_user_cascades(db_session: tuple[Session, int, int]) -> None:
    """ON DELETE CASCADE: no orphan games, and no orphan moves under those."""
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    repo.add_move(game, uci="e2e4", san="e4", move_number=1)
    game_id = game.id
    session.commit()

    user = session.get(User, user1_id)
    assert user is not None
    session.delete(user)
    session.commit()

    # `game_id` was captured before the cascade: the row is gone, so touching
    # the expired instance would raise rather than answer the question.
    assert session.execute(select(Game)).all() == []
    assert session.execute(select(GameMove).where(GameMove.game_id == game_id)).all() == []


def test_status_check_constraint_rejects_unknown_value(
    db_session: tuple[Session, int, int],
) -> None:
    """The domain enum is enforced by the database, not only by Python."""
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    game.status = "undecided"
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_recover_game_with_moves(db_session: tuple[Session, int, int]) -> None:
    """Test game recovery with full move history."""
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    repo.add_move(game, uci="e2e4", san="e4", move_number=1)
    repo.add_move(game, uci="e7e5", san="e5", move_number=2)

    recovered = repo.recover_game(game.id, user_id=user1_id)
    assert recovered is not None
    recovered_game, moves = recovered
    assert recovered_game.id == game.id
    assert len(moves) == 2
    assert moves[0].uci == "e2e4"
    assert moves[1].uci == "e7e5"


def test_recover_game_ownership_enforced(db_session: tuple[Session, int, int]) -> None:
    """Test that game recovery enforces ownership."""
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = _create_game(repo, user1_id)
    repo.add_move(game, uci="e2e4", san="e4", move_number=1)

    # Different user cannot recover
    assert repo.recover_game(game.id, user_id=user2_id) is None
