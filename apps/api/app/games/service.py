"""Game service: rules validation + persistence (API-005..012).

Layering (per code-standards): routes validate HTTP input and call this
service; the service uses `ChessRules` for chess logic and `GameRepository`
for persistence.

Three invariants hold every write together:

* **One transaction per operation.** Repositories flush, this layer commits via
  :func:`app.core.unit_of_work.transaction`. A move row and the game state it
  belongs to either both land or both disappear, so a rejected move cannot
  leave an orphan row behind.
* **Conditional state writes.** The optimistic-version check is folded into the
  ``UPDATE`` itself (``apply_state``), never read-then-write. A lost update
  surfaces as ``rowcount == 0`` and becomes :class:`StaleVersionError` (409).
* **The engine search never holds a transaction.** In computer mode the human
  ply commits first, then the reply is searched behind the provider seam with no
  open row lock, then written through the same conditional update — so a slow or
  dead engine degrades instead of blocking the database.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.unit_of_work import transaction
from app.engine.domain import EngineDifficulty, difficulty_from_level
from app.engine.runtime import get_engine_provider, get_search_limiter
from app.games.domain import (
    STARTING_FEN,
    Color,
    EndReason,
    EngineLevel,
    GameMode,
    GameResult,
    GameStatus,
    Move,
    format_pgn,
)
from app.games.errors import IllegalMoveError, InvalidMoveError
from app.games.rules import ChessRules
from app.models.game import Game as GameRow
from app.models.game_move import GameMove as GameMoveRow
from app.repositories.game_repository import GameRepository


@dataclass(frozen=True)
class GameDetail:
    """A game row plus its ordered move history and a derived ``in_check`` flag."""

    game: GameRow
    moves: list[GameMoveRow]
    in_check: bool = False


@dataclass(frozen=True)
class GameSummary:
    """A lightweight, listable view of one game (no move payloads)."""

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


class GameNotFoundError(Exception):
    """Game id unknown or owned by another user (mapped to 404)."""


class StaleVersionError(Exception):
    """Optimistic-concurrency version mismatch (mapped to 409)."""


class IllegalMoveRequestError(Exception):
    """UCI unparsable, illegal, wrong side to move, or bad claim (mapped to 422)."""


class GameFinishedError(Exception):
    """State change requested on a finished game (mapped to 409)."""


# ---------------------------------------------------------------- lookups


def _require_game(repo: GameRepository, game_id: int, user_id: int) -> GameRow:
    game = repo.get_by_id(game_id, user_id)
    if game is None:
        raise GameNotFoundError(f"Game {game_id} not found")
    return game


def _require_active(game: GameRow) -> None:
    if game.status != GameStatus.ACTIVE.value:
        raise GameFinishedError(f"Game is {game.status}")


def _require_version(game: GameRow, expected_version: int) -> None:
    """Reject writes based on a stale client snapshot (optimistic concurrency)."""
    if game.version != expected_version:
        raise StaleVersionError(
            f"Game changed elsewhere: you sent version {expected_version} "
            f"but the game is now at version {game.version}"
        )


def _rules_for(game: GameRow, moves: Sequence[GameMoveRow]) -> ChessRules:
    """Rebuild the position from the stored move history.

    A board built from a bare FEN has no ``move_stack``, so python-chess cannot
    see a threefold repetition on it (CHS-014). Every persisted game keeps its
    full UCI history, so replaying it is the correct way to evaluate status.
    Games always start from ``STARTING_FEN`` (see :func:`create_game`), which
    makes the replay exact; if history ever fails to reproduce, the stored FEN
    is still the safer fallback for legality checks than a hard error.
    """
    ucis = [m.uci for m in moves]
    try:
        return ChessRules.from_moves(ucis, STARTING_FEN)
    except (InvalidMoveError, IllegalMoveError):
        return ChessRules(game.fen)


def _build_rules(repo: GameRepository, game: GameRow) -> ChessRules:
    """Rules for the current position, replayed from the stored history."""
    return _rules_for(game, repo.get_moves(game.id, game.user_id))


def _player_color(game: GameRow) -> Color:
    return Color(game.player_color)


def _engine_color(game: GameRow) -> Color:
    """The side the engine plays in a computer game (opposite of the player)."""
    player = _player_color(game)
    return Color.BLACK if player == Color.WHITE else Color.WHITE


# ------------------------------------------------------- outcome attribution


@dataclass(frozen=True)
class _Outcome:
    """Terminal fields (status + attribution) for a freshly played position."""

    status: str
    end_reason: str | None
    winner: str | None
    result: str


def _outcome_after(game: GameRow, rules: ChessRules) -> _Outcome:
    """Derive status and PGN attribution from the position after a move.

    The already-terminal case passes the stored outcome straight through, so a
    later, unrelated write cannot clobber a finished game's result. Checkmate is
    credited to the side *not* to move (the mover has no legal reply). Stalemate
    and every draw form share ``1/2-1/2`` with no winner.
    """
    if game.status != GameStatus.ACTIVE.value:
        return _Outcome(game.status, game.end_reason, game.winner, game.result)
    status = rules.status()
    if status == GameStatus.ACTIVE:
        return _Outcome(GameStatus.ACTIVE.value, None, None, GameResult.OPEN.value)
    if status == GameStatus.CHECKMATE:
        # rules.turn is the checkmated side; the winner is the other colour.
        winner = Color.BLACK if rules.turn == Color.WHITE else Color.WHITE
        result = GameResult.WHITE_WIN if winner == Color.WHITE else GameResult.BLACK_WIN
        return _Outcome(
            GameStatus.CHECKMATE.value, EndReason.CHECKMATE.value, winner.value, result.value
        )
    if status == GameStatus.STALEMATE:
        return _Outcome(
            GameStatus.STALEMATE.value, EndReason.STALEMATE.value, None, GameResult.DRAW.value
        )
    return _Outcome(GameStatus.DRAW.value, EndReason.DRAW.value, None, GameResult.DRAW.value)


def _apply_state(
    repo: GameRepository, game: GameRow, fen: str, outcome: _Outcome, expected_version: int
) -> None:
    """Conditional write; zero rows touched means somebody else got there first."""
    if (
        repo.apply_state(
            game,
            fen=fen,
            status=outcome.status,
            expected_version=expected_version,
            end_reason=outcome.end_reason,
            winner=outcome.winner,
            result=outcome.result,
        )
        == 0
    ):
        raise StaleVersionError(
            f"Game {game.id} changed while this request was in flight; "
            f"version {expected_version} is no longer current"
        )


def _record_move(repo: GameRepository, game: GameRow, move: Move) -> GameMoveRow:
    """Insert the next ply, claiming its number from a count inside the transaction.

    ``UNIQUE (game_id, move_number)`` is the backstop: if another writer claimed
    the same ply first, the conflict becomes a 409 instead of a corrupt history.
    """
    try:
        return repo.add_move(
            game, uci=move.uci, san=move.san, move_number=repo.count_moves(game.id) + 1
        )
    except IntegrityError as exc:
        raise StaleVersionError(
            f"Game {game.id} move {move.uci} collided with a concurrent write"
        ) from exc


def _detail_after_commit(db: Session, repo: GameRepository, game: GameRow) -> GameDetail:
    """Re-read the row after commit so callers see server-side truth.

    ``expire_on_commit`` means attribute access would lazily re-SELECT inside
    the response; doing it explicitly here keeps the read inside the request's
    session and makes the version/fen the caller must use next unambiguous.
    """
    fresh = _require_game(repo, game.id, game.user_id)
    return _make_detail(fresh, repo.get_moves(fresh.id, fresh.user_id))


def _make_detail(game: GameRow, moves: list[GameMoveRow]) -> GameDetail:
    """Bundle a row + history with the ``in_check`` the frontend should not guess.

    Derived from the replayed position (the same board the rules engine uses),
    so it agrees with legality and status checks instead of a FEN substring.
    """
    return GameDetail(game=game, moves=moves, in_check=_rules_for(game, moves).is_check())


# -------------------------------------------------------------------- create


def create_game(
    db: Session,
    user_id: int,
    mode: str,
    player_color: str = Color.WHITE.value,
    engine_level: str = EngineLevel.MEDIUM.value,
) -> GameDetail:
    """Create a game in the starting position (API-005).

    A computer game where the player takes Black opens with an engine move, so
    the very first response already carries Stockfish's opening reply — the loop
    is real from the first request, not a shared board the user must drive.
    """
    try:
        game_mode = GameMode(mode)
    except ValueError as exc:
        raise IllegalMoveRequestError(f"Invalid mode: {mode!r}") from exc
    try:
        color = Color(player_color)
    except ValueError as exc:
        raise IllegalMoveRequestError(f"Invalid player_color: {player_color!r}") from exc
    try:
        level = EngineLevel(engine_level)
    except ValueError as exc:
        raise IllegalMoveRequestError(f"Invalid engine_level: {engine_level!r}") from exc

    repo = GameRepository(db)
    with transaction(db):
        game = repo.create(
            user_id=user_id,
            mode=game_mode.value,
            fen=STARTING_FEN,
            player_color=color.value,
            engine_level=level.value,
        )

    detail = GameDetail(game=game, moves=[])
    if game_mode == GameMode.COMPUTER and color == Color.BLACK:
        # Engine plays White's opening move.
        detail = _play_engine_ply(
            db, repo, game.id, user_id, game.version, difficulty_from_level(level.value)
        )
    return detail


# --------------------------------------------------------------------- reads


def list_game_summaries(
    db: Session, user_id: int, *, status: str | None = None, limit: int = 20, offset: int = 0
) -> tuple[list[GameSummary], int]:
    """One page of game summaries plus the caller's total (kills the list N+1)."""
    repo = GameRepository(db)
    rows = repo.list_summaries(user_id, status=status, limit=limit, offset=offset)
    summaries = [
        GameSummary(
            id=row.id,
            mode=row.mode,
            status=row.status,
            player_color=row.player_color,
            engine_level=row.engine_level,
            result=row.result,
            winner=row.winner,
            version=row.version,
            move_count=int(row.move_count),
            last_played_at=row.last_played_at,
        )
        for row in rows
    ]
    total = repo.count_games(user_id, status=status)
    return summaries, total


def get_game(db: Session, game_id: int, user_id: int) -> GameDetail:
    """Fetch a game with its move history (API-007)."""
    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    return _make_detail(game, repo.get_moves(game_id, user_id))


def get_pgn(db: Session, game_id: int, user_id: int) -> str:
    """Render the game as a standards-following PGN document (API-020)."""
    detail = get_game(db, game_id, user_id)
    game = detail.game
    sans = [m.san for m in detail.moves]
    if game.mode == GameMode.COMPUTER.value:
        player = _player_color(game)
        white_name = "Player" if player == Color.WHITE else "Engine"
        black_name = "Player" if player == Color.BLACK else "Engine"
    else:
        white_name, black_name = "White", "Black"
    return format_pgn(sans, result=game.result, white_name=white_name, black_name=black_name)


def compute_stats(db: Session, user_id: int) -> dict[str, dict[str, int]]:
    """Wins/losses/draws by mode, from a single aggregate query (API-021)."""
    return GameRepository(db).stats(user_id)


# ------------------------------------------------------------- move handling


def submit_move(
    db: Session, game_id: int, user_id: int, uci: str, expected_version: int
) -> GameDetail:
    """Validate a UCI move, persist it, and auto-reply in computer mode.

    The conditional state write comes *first*: if the version is stale we raise
    before a move row is even created, so the rejected ply can never collide
    with the winner's row inside the same transaction. In computer mode the
    engine then answers, and both plies ship in this one response — the client
    never has to ask twice and the version chain stays intact.
    """
    repo = GameRepository(db)
    detail = _apply_human_move(db, repo, game_id, user_id, uci, expected_version)
    game = detail.game
    if game.mode == GameMode.COMPUTER.value and game.status == GameStatus.ACTIVE.value:
        # After the human ply it is the engine's colour to move; reply if so.
        rules = _rules_for(game, detail.moves)
        if rules.turn == _engine_color(game):
            detail = _play_engine_ply(
                db, repo, game_id, user_id, game.version, difficulty_from_level(game.engine_level)
            )
    return detail


def _apply_human_move(
    db: Session,
    repo: GameRepository,
    game_id: int,
    user_id: int,
    uci: str,
    expected_version: int,
) -> GameDetail:
    """Apply the human's ply in one transaction (and enforce side in computer mode)."""
    with transaction(db):
        game = _require_game(repo, game_id, user_id)
        _require_active(game)
        _require_version(game, expected_version)
        rules = _build_rules(repo, game)
        if game.mode == GameMode.COMPUTER.value and rules.turn != _player_color(game):
            raise IllegalMoveRequestError("It is the engine's move; play only on your own turn")
        try:
            move = rules.apply_move(uci)
        except (InvalidMoveError, IllegalMoveError) as exc:
            raise IllegalMoveRequestError(str(exc)) from exc
        _apply_state(
            repo,
            game,
            fen=rules.fen,
            outcome=_outcome_after(game, rules),
            expected_version=expected_version,
        )
        _record_move(repo, game, move)
    return _detail_after_commit(db, repo, game)


def _play_engine_ply(
    db: Session,
    repo: GameRepository,
    game_id: int,
    user_id: int,
    expected_version: int,
    level: EngineDifficulty,
) -> GameDetail:
    """Play one engine ply: read, search outside the transaction, then write.

    The search runs with **no open DB transaction** (Phase 2 cost control): read
    and validate, commit to release the row, search behind the provider seam
    (circuit + limiter), then write through the conditional update. Shared by
    :func:`submit_move` (auto-reply), :func:`create_game` (opening), and the
    public ``/engine-move`` route.
    """
    from app.models.engine_run import EngineRun

    # Phase A — read + validate, then commit to release any row snapshot.
    with transaction(db):
        game = _require_game(repo, game_id, user_id)
        _require_active(game)
        if game.mode != GameMode.COMPUTER.value:
            raise IllegalMoveRequestError("Engine moves require a computer game")
        _require_version(game, expected_version)
        rules = _build_rules(repo, game)
        if rules.status() != GameStatus.ACTIVE:
            raise GameFinishedError("Game is over")
        if rules.turn != _engine_color(game):
            raise IllegalMoveRequestError("It is not the engine's turn")
        searched_fen = rules.fen

    # Phase B — search outside the transaction, guarded by the limiter.
    provider = get_engine_provider()
    limiter = get_search_limiter()
    with limiter.slot(user_id):
        result = provider.move_for(searched_fen, level=level)
    if not result.best_move:
        raise IllegalMoveRequestError("Engine returned no move")

    # Phase C — write the ply. Re-fetch (expired by Phase A's commit) and
    # re-check the version so a concurrent mover collides into a 409, not a
    # corrupt history.
    with transaction(db):
        game = _require_game(repo, game_id, user_id)
        _require_active(game)
        _require_version(game, expected_version)
        try:
            move = rules.apply_move(result.best_move)
        except (InvalidMoveError, IllegalMoveError) as exc:
            raise IllegalMoveRequestError(f"Engine returned bad move: {exc}") from exc
        _apply_state(
            repo,
            game,
            fen=rules.fen,
            outcome=_outcome_after(game, rules),
            expected_version=expected_version,
        )
        _record_move(repo, game, move)
        db.add(
            EngineRun(
                game_id=game.id,
                fen=searched_fen,
                best_move=move.uci,
                score=result.score,
                depth=result.depth,
                nodes_searched=result.nodes_searched,
                time_ms=result.time_ms,
            )
        )
    return _detail_after_commit(db, repo, game)


def request_engine_move(
    db: Session,
    game_id: int,
    user_id: int,
    expected_version: int,
) -> GameDetail:
    """Let the engine play only when it is genuinely its turn (API-012).

    Difficulty comes from the stored game, never the client. Kept as a public
    seam so a caller can nudge a stuck reply, but it now refuses to move for the
    human's colour.
    """
    repo = GameRepository(db)
    with transaction(db):
        game = _require_game(repo, game_id, user_id)
        _require_active(game)
        _require_version(game, expected_version)
        level = difficulty_from_level(game.engine_level)
    return _play_engine_ply(db, repo, game_id, user_id, expected_version, level)


def undo_move(db: Session, game_id: int, user_id: int, expected_version: int) -> GameDetail:
    """Undo the last move (API-009).

    In computer mode a single human turn is really a *pair* — the player's move
    plus the engine's reply — so undo removes both and leaves the human on move
    again, in one transaction.
    """
    repo = GameRepository(db)
    with transaction(db):
        game = _require_game(repo, game_id, user_id)
        _require_active(game)
        _require_version(game, expected_version)
        moves = repo.get_moves(game_id, user_id)
        if not moves:
            raise IllegalMoveRequestError("No moves to undo")
        drop = 2 if game.mode == GameMode.COMPUTER.value else 1
        surviving = moves[:-drop] if len(moves) >= drop else []
        # Replay the surviving history: exact position *and* repetition context.
        rules = _rules_for(game, surviving)
        _apply_state(
            repo,
            game,
            fen=rules.fen,
            outcome=_Outcome(GameStatus.ACTIVE.value, None, None, GameResult.OPEN.value),
            expected_version=expected_version,
        )
        for move_row in moves[len(surviving) :]:
            repo.delete_move(move_row)
    return _detail_after_commit(db, repo, game)


def resign_game(db: Session, game_id: int, user_id: int) -> GameDetail:
    """Mark an active game resigned, attributing the win to the other side (API-010)."""
    repo = GameRepository(db)
    with transaction(db):
        game = _require_game(repo, game_id, user_id)
        _require_active(game)
        # The resigning side: the human's colour in a computer game, otherwise
        # whoever is to move. The winner is the opposite side.
        rules = _build_rules(repo, game)
        resigner = _player_color(game) if game.mode == GameMode.COMPUTER.value else rules.turn
        winner = Color.BLACK if resigner == Color.WHITE else Color.WHITE
        result = GameResult.WHITE_WIN if winner == Color.WHITE else GameResult.BLACK_WIN
        if (
            repo.mark_finished(
                game,
                GameStatus.RESIGNED.value,
                end_reason=EndReason.RESIGNATION.value,
                winner=winner.value,
                result=result.value,
            )
            == 0
        ):
            current = _require_game(repo, game_id, user_id)
            raise GameFinishedError(f"Game is {current.status}")
    return _detail_after_commit(db, repo, game)


def claim_draw(db: Session, game_id: int, user_id: int) -> GameDetail:
    """Claim a draw when the position supports it (API-011)."""
    repo = GameRepository(db)
    with transaction(db):
        game = _require_game(repo, game_id, user_id)
        _require_active(game)
        rules = _build_rules(repo, game)
        if not _supports_draw(rules):
            raise IllegalMoveRequestError("Position does not support a draw claim")
        if (
            repo.mark_finished(
                game,
                GameStatus.DRAW.value,
                end_reason=EndReason.DRAW.value,
                result=GameResult.DRAW.value,
            )
            == 0
        ):
            current = _require_game(repo, game_id, user_id)
            raise GameFinishedError(f"Game is {current.status}")
    return _detail_after_commit(db, repo, game)


def _supports_draw(rules: ChessRules) -> bool:
    """Draw claims are backed by the replayed history, not by the FEN alone."""
    return (
        rules.status() == GameStatus.DRAW
        or rules.is_fifty_moves()
        or rules.is_repetition(3)
        or rules.is_stalemate()
        or rules.is_insufficient_material()
    )
