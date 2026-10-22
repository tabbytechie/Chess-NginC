"""Game repository: ownership-scoped reads and flush-only writes.

Two rules keep game state consistent under concurrency:

1. **No commits here.** The unit of work belongs to the service layer
   (:mod:`app.core.unit_of_work`), so a move insert and the state update it
   belongs to either both land or both roll back.
2. **State writes are conditional.** ``apply_state`` folds the version check
   into the ``UPDATE`` itself instead of reading, comparing, then writing —
   the read-modify-write it replaced lost updates between two sessions.

Ownership is enforced inside every statement. Writes take an already-loaded
``Game`` row, which means a caller cannot write to a game it could not read.
"""

from datetime import datetime
from typing import NamedTuple

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.games.domain import Color, EngineLevel, GameStatus
from app.models.game import Game
from app.models.game_move import GameMove


class GameSummaryRow(NamedTuple):
    """One row of the paginated game list (see :meth:`GameRepository.list_summaries`)."""

    id: int
    mode: str
    status: str
    player_color: str
    engine_level: str
    result: str
    winner: str | None
    version: int
    move_count: int
    last_played_at: datetime


class GameRepository:
    """Repository for game data access with ownership enforcement."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------------------------------------------------------- reads

    def get_by_id(self, game_id: int, user_id: int) -> Game | None:
        """Get a game by ID, enforcing ownership."""
        stmt = select(Game).where(Game.id == game_id, Game.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_moves(self, game_id: int, user_id: int) -> list[GameMove]:
        """Get all moves for a game, enforcing ownership in the same query."""
        stmt = (
            select(GameMove)
            .join(Game, Game.id == GameMove.game_id)
            .where(GameMove.game_id == game_id, Game.user_id == user_id)
            .order_by(GameMove.move_number)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_moves(self, game_id: int) -> int:
        """Number of stored moves — the ply the next write should claim."""
        stmt = select(func.count()).select_from(GameMove).where(GameMove.game_id == game_id)
        return int(self.db.execute(stmt).scalar_one())

    def recover_game(self, game_id: int, user_id: int) -> tuple[Game, list[GameMove]] | None:
        """Recover a game with all its moves, enforcing ownership.

        Returns (game, moves) tuple or None if not found or ownership violation.
        """
        game = self.get_by_id(game_id, user_id)
        if game is None:
            return None
        return game, self.get_moves(game_id, user_id)

    def list_summaries(
        self, user_id: int, *, status: str | None = None, limit: int = 20, offset: int = 0
    ) -> list[GameSummaryRow]:
        """One page of the caller's games with move count and last-played time.

        A single ``LEFT JOIN`` aggregate replaces the old ``GET /games`` that
        re-ran ``get_game`` per row (an N+1). ``last_played_at`` falls back to
        ``games.updated_at`` for a game with no moves yet.
        """
        move_agg = (
            select(
                GameMove.game_id.label("game_id"),
                func.count().label("move_count"),
                func.max(GameMove.created_at).label("last_played_at"),
            )
            .group_by(GameMove.game_id)
            .subquery()
        )
        stmt = (
            select(
                Game.id,
                Game.mode,
                Game.status,
                Game.player_color,
                Game.engine_level,
                Game.result,
                Game.winner,
                Game.version,
                func.coalesce(move_agg.c.move_count, 0).label("move_count"),
                func.coalesce(move_agg.c.last_played_at, Game.updated_at).label("last_played_at"),
            )
            .outerjoin(move_agg, move_agg.c.game_id == Game.id)
            .where(Game.user_id == user_id)
        )
        if status is not None:
            stmt = stmt.where(Game.status == status)
        stmt = stmt.order_by(Game.id.desc()).limit(limit).offset(offset)
        return [GameSummaryRow(*row) for row in self.db.execute(stmt).all()]

    def count_games(self, user_id: int, *, status: str | None = None) -> int:
        """Total games for the caller (the pagination ``total``)."""
        stmt = select(func.count()).select_from(Game).where(Game.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Game.status == status)
        return int(self.db.execute(stmt).scalar_one())

    def stats(self, user_id: int) -> dict[str, dict[str, int]]:
        """Wins/losses/draws by mode from one aggregate query.

        A *win* is a finished game whose ``winner`` equals the player's own
        colour; a *loss* has a winner on the other side; a *draw* carries no
        winner but a decisive-free result. Grouping by mode lets the dashboard
        separate pass-and-play from bot results.
        """
        active = Game.status == GameStatus.ACTIVE.value
        finished = and_(~active)
        win = case(
            (and_(finished, Game.winner.isnot(None), Game.winner == Game.player_color), 1),
            else_=0,
        )
        loss = case(
            (and_(finished, Game.winner.isnot(None), Game.winner != Game.player_color), 1),
            else_=0,
        )
        draw = case(
            (and_(finished, Game.winner.is_(None), Game.result == "1/2-1/2"), 1),
            else_=0,
        )
        played = case((finished, 1), else_=0)
        stmt = (
            select(
                Game.mode,
                func.coalesce(func.sum(win), 0),
                func.coalesce(func.sum(loss), 0),
                func.coalesce(func.sum(draw), 0),
                func.coalesce(func.sum(played), 0),
                func.count(),
            )
            .where(Game.user_id == user_id)
            .group_by(Game.mode)
        )
        out: dict[str, dict[str, int]] = {}
        for mode, wins, losses, draws, finished, total in self.db.execute(stmt).all():
            out[mode] = {
                "wins": int(wins),
                "losses": int(losses),
                "draws": int(draws),
                "finished": int(finished),
                "total": int(total),
            }
        return out

    # --------------------------------------------------------------- writes

    def create(
        self,
        user_id: int,
        mode: str,
        fen: str,
        *,
        player_color: str = Color.WHITE.value,
        engine_level: str = EngineLevel.MEDIUM.value,
    ) -> Game:
        """Create a new game for the user (flushed, not committed)."""
        game = Game(
            user_id=user_id,
            mode=mode,
            status=GameStatus.ACTIVE.value,
            fen=fen,
            player_color=player_color,
            engine_level=engine_level,
        )
        self.db.add(game)
        self.db.flush()
        return game

    def add_move(self, game: Game, uci: str, san: str, move_number: int) -> GameMove:
        """Attach a move to an already ownership-checked game row.

        Raises ``IntegrityError`` at commit time if another writer already
        claimed ``move_number`` for this game.
        """
        move = GameMove(game_id=game.id, uci=uci, san=san, move_number=move_number)
        self.db.add(move)
        self.db.flush()
        return move

    def delete_move(self, move: GameMove) -> None:
        """Remove one move row (flushed; the caller commits)."""
        self.db.delete(move)
        self.db.flush()

    def apply_state(
        self,
        game: Game,
        fen: str,
        status: str,
        expected_version: int,
        *,
        end_reason: str | None = None,
        winner: str | None = None,
        result: str | None = None,
    ) -> int:
        """Atomically write the new position, status, version, and outcome.

        Returns the number of rows updated: ``0`` means the version moved on
        underneath us and the caller must raise, never retry blindly. The
        outcome columns are only written when supplied (a game that just became
        terminal), so an in-progress move leaves them untouched.
        """
        values: dict[str, object] = {
            "fen": fen,
            "status": status,
            "version": Game.version + 1,
            "updated_at": utc_now(),
        }
        if end_reason is not None:
            values["end_reason"] = end_reason
        if winner is not None:
            values["winner"] = winner
        if result is not None:
            values["result"] = result
        stmt = (
            update(Game)
            .where(
                Game.id == game.id,
                Game.user_id == game.user_id,
                Game.version == expected_version,
            )
            .values(**values)
            # Keep the in-memory row truthful: the service reads the game again
            # after this statement, and a stale `version` there would make the
            # next conditional write fail for the wrong reason.
            .execution_options(synchronize_session="evaluate")
        )
        # `rowcount` is a Cursor-family attribute; SQLAlchemy's Result exposes it
        # for DML statements but the base Result type does not advertise it.
        return int(self.db.execute(stmt).rowcount or 0)  # type: ignore[attr-defined]

    def mark_finished(
        self,
        game: Game,
        status: str,
        *,
        end_reason: str | None = None,
        winner: str | None = None,
        result: str | None = None,
    ) -> int:
        """Move an *active* game to a terminal status exactly once.

        Guarded on ``status = 'active'`` rather than a client version, so two
        simultaneous resignations cannot both take effect.
        """
        values: dict[str, object] = {
            "status": status,
            "version": Game.version + 1,
            "updated_at": utc_now(),
        }
        if end_reason is not None:
            values["end_reason"] = end_reason
        if winner is not None:
            values["winner"] = winner
        if result is not None:
            values["result"] = result
        stmt = (
            update(Game)
            .where(
                Game.id == game.id,
                Game.user_id == game.user_id,
                Game.status == GameStatus.ACTIVE.value,
            )
            .values(**values)
            .execution_options(synchronize_session="evaluate")
        )
        return int(self.db.execute(stmt).rowcount or 0)  # type: ignore[attr-defined]
