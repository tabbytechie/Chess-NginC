"""Post-game review service (REVIEW-001..005).

Replays a finished game ply by ply through the Stockfish provider (review
bounds: deeper/longer than live play), grades every move with the classifier,
writes a coaching line with the explainer, and stores the assembled JSON in
`game_reviews` so GET serves it without re-analysis.

One analysis per distinct position, and the positions are chained: the score of
position N+1 is the value the move played in position N actually left on the
board. That is what grades a move the MultiPV window never ranked (TD-009), and
it costs no extra searches — the next ply's position was going to be analysed
anyway. The whole pass runs against one warm engine process (ANL-003).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import chess
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.rag.index import index_review_safe
from app.core.telemetry import engine_timer, record_engine_unavailable
from app.engine.classifier import (
    MoveContext,
    MoveQuality,
    centipawn_loss,
    classify_move,
)
from app.engine.factory import open_stockfish_provider
from app.engine.provider import (
    AnalyseRequest,
    AnalysisResult,
    EngineProvider,
    PrincipalVariation,
)
from app.engine.stockfish import StockfishUnavailableError
from app.games.domain import Color, GameMode, GameStatus
from app.games.errors import EngineUnavailableError
from app.games.service import GameNotFoundError
from app.models.game import Game as GameRow
from app.models.game_move import GameMove as GameMoveRow
from app.models.game_review import GameReview
from app.reviews.explainer import explain_move

CAPTURE_VALUE_CP = {"p": 100, "n": 300, "b": 300, "r": 500, "q": 900}
# MultiPV width per position: best + enough alternatives that a decent played
# move is covered. A move outside the window is graded from the value of the
# position it produced (see `_line_score`), not from this constant.
REVIEW_MULTIPV = 3
REVIEW_DEPTH = 15
REVIEW_TIME_MS = 1000
# Mate magnitude, matching the adapter's convention so a terminal position and
# an engine mate score are on the same ruler.
MATE_CP = 20_000
# Last resort when neither the window nor the following position says anything
# (an engine that returned no lines at all): pessimistic, so it grades blunder.
_OFF_TABLE_CP = -800


class ReviewTargetError(Exception):
    """Game exists but cannot be reviewed (still active / no moves) → 422."""


@dataclass(frozen=True)
class _Ply:
    """One replayed move: the chess facts needed to grade it, plus the three
    stored scalars the payload echoes.

    RB-002: these are plain values, not the ORM row, on purpose — the review
    analysis runs after the session has released its connection, and reading
    a row attribute after that would silently re-acquire one.
    """

    pre_fen: str
    mover: chess.Color
    move: chess.Move
    is_forced: bool
    was_checked: bool
    captures_value_cp: int
    move_number: int
    uci: str
    san: str


def _game_moves(db: Session, game_id: int) -> list[GameMoveRow]:
    """All moves of a game in order.

    Deliberately not `GameRepository.get_moves`: that filters by the owner
    column, which mirrors the White seat — an online Black reviewer must
    still see every ply.
    """
    stmt = (
        select(GameMoveRow).where(GameMoveRow.game_id == game_id).order_by(GameMoveRow.move_number)
    )
    return list(db.execute(stmt).scalars().all())


def _color_domain(mover: chess.Color) -> Color:
    return Color.WHITE if mover == chess.WHITE else Color.BLACK


def hero_color_for(game: GameRow, user_id: int) -> str:
    """Which color the requesting player is reviewed as."""
    if game.mode == GameMode.COMPUTER.value:
        return "w"  # the account owner always plays White vs the computer
    if game.mode == GameMode.ONLINE.value:
        if game.white_user_id == user_id:
            return "w"
        if game.black_user_id == user_id:
            return "b"
        raise GameNotFoundError(f"Game {game.id} not found")
    return "w"  # local hot-seat: review White's side


def get_existing(db: Session, game_id: int, user_id: int) -> GameReview | None:
    stmt = select(GameReview).where(GameReview.game_id == game_id, GameReview.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def load_game(db: Session, game_id: int, user_id: int) -> GameRow:
    """Owner-visible games, plus online games where the user holds a seat."""
    game = db.get(GameRow, game_id)
    if game is None:
        raise GameNotFoundError(f"Game {game_id} not found")
    if game.user_id != user_id and game.white_user_id != user_id and game.black_user_id != user_id:
        raise GameNotFoundError(f"Game {game_id} not found")
    return game


def _flip(cp: int, mate_in: int | None) -> tuple[int, int | None]:
    """Re-read a score from the other side's point of view.

    The provider returns every line from the side to move's view; the mover of
    the previous ply is the *opponent* of the side to move in the resulting
    position, so their best score is the mover's worst news.
    """
    return -cp, None if mate_in is None else -mate_in


def _terminal_value(post: chess.Board, mover: chess.Color) -> tuple[int, int | None]:
    """Score a finished position leaves the mover with, from the mover's view.

    Chess rules decide this exactly, so the engine is never asked about a dead
    position (it answers those with no lines at all).
    """
    if post.is_checkmate():
        mate_for_mover = (post.turn == chess.BLACK) == (mover == chess.WHITE)
        cp = MATE_CP - 10
        return (cp, 1) if mate_for_mover else (-cp, -1)
    return 0, None


def _line_score(
    lines: tuple[PrincipalVariation, ...],
    move_uci: str,
    position_value: tuple[int, int | None] | None,
) -> tuple[int, int | None, bool]:
    """(cp, mate_in, is_best) for the move that was actually played.

    Inside the MultiPV window, the engine's own number for that exact move wins.
    Outside it, `position_value` — what the move really left on the board, read
    from the next position's analysis — replaces the old flat ``-800``, so a move
    that hands over a pawn is graded like losing a pawn instead of always being
    called a blunder because the search ranked three other moves higher.
    """
    best = lines[0] if lines else None
    for line in lines:
        if line.move == move_uci:
            return line.score_cp, line.mate_in, best is not None and best.move == line.move
    if position_value is not None:
        return position_value[0], position_value[1], False
    if best is not None:
        return best.score_cp + _OFF_TABLE_CP, None, False
    return 0, None, False


def _analyse(provider: EngineProvider, fen: str, mover: chess.Color) -> AnalysisResult:
    """One bounded analysis of one position, from the mover's perspective."""
    return provider.analyse(
        AnalyseRequest(
            fen=fen,
            depth=REVIEW_DEPTH,
            multipv=REVIEW_MULTIPV,
            max_time_ms=REVIEW_TIME_MS,
            for_color=_color_domain(mover),
        )
    )


def _replay(moves: list[GameMoveRow]) -> tuple[list[_Ply], chess.Board]:
    """Walk the stored moves once, collecting the chess facts per ply.

    Validation happens before any engine call: an unparsable or illegal stored
    move must not cost a search (or a partially graded review).
    """
    board = chess.Board()
    plies: list[_Ply] = []
    for row in moves:
        pre_fen = board.fen()
        mover = board.turn
        try:
            move = chess.Move.from_uci(row.uci)
        except ValueError as exc:
            raise ReviewTargetError(f"Stored move {row.uci!r} is unparsable") from exc
        if move not in board.legal_moves:
            raise ReviewTargetError(f"Stored move {row.uci!r} is not legal in the replay")
        is_forced = len(list(board.legal_moves)) == 1
        was_checked = board.is_check()
        captures = _captures_value(board, move)
        board.push(move)
        plies.append(
            _Ply(
                pre_fen=pre_fen,
                mover=mover,
                move=move,
                is_forced=is_forced,
                was_checked=was_checked,
                captures_value_cp=captures,
                move_number=row.move_number,
                uci=row.uci,
                san=row.san,
            )
        )
    return plies, board


def _position_value(
    index: int,
    plies: list[_Ply],
    analyses: list[AnalysisResult],
    tail: AnalysisResult | None,
    final_board: chess.Board,
) -> tuple[int, int | None] | None:
    """Value of the position ply `index` produced, seen from that ply's mover.

    ``None`` only when nothing was learned: the last ply ended the game in a
    position the rules cannot score (impossible — a finished game is checkmate or
    a draw) or an engine that returned no lines for the following position.
    """
    if index + 1 < len(plies):
        following: AnalysisResult | None = analyses[index + 1]
    elif final_board.is_game_over():
        return _terminal_value(final_board, plies[index].mover)
    else:
        following = tail
    if following is None or not following.lines:
        return None
    return _flip(following.lines[0].score_cp, following.lines[0].mate_in)


def _captures_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return CAPTURE_VALUE_CP["p"]
    victim = board.piece_at(move.to_square)
    if victim is None:
        return 0
    # `Piece.symbol()` is color-cased ('P' vs 'p'), so a White victim — any
    # capture by Black — used to look like free material worth nothing, which
    # quietly denied Black the sacrifice grade and the capture context.
    return CAPTURE_VALUE_CP.get(victim.symbol().lower(), 0)


# Average-centipawn-loss scale for the accuracy figure: a game averaging this
# much loss per move scores ~37 (e^-1), so a strong game (acl ~10) lands near 96
# and a beginner one (acl ~100) near 67.
ACCURACY_LOSS_SCALE_CP = 250


def _accuracy(losses: list[int]) -> int:
    """Accuracy 0..100 from average centipawn loss: flawless play is 100 and
    the figure decays smoothly as the average loss grows.

    The first version of this mapped loss the wrong way round
    (`103 * (1 - e^(-acl/150))`) and handed 0% to a game with no errors at all.
    Still an approximation, not a rating-calibrated model (CLS-004 / TD-016).
    """
    if not losses:
        return 100
    acl = sum(losses) / len(losses)
    return max(0, min(100, round(100 * math.exp(-acl / ACCURACY_LOSS_SCALE_CP))))


def analyse_game(provider: EngineProvider, moves: list[GameMoveRow]) -> dict:
    """Classify every ply from the starting position; build the review payload."""
    plies, final_board = _replay(moves)
    return analyse_plies(provider, plies, final_board)


def analyse_plies(provider: EngineProvider, plies: list[_Ply], final_board: chess.Board) -> dict:
    """Grade an already-replayed game (RB-002).

    Takes the detached `_Ply` scalars, not ORM rows, so the caller can release
    the DB connection across the seconds of engine work and hand the finished
    payload to a short write transaction.
    """
    # One search per position the game actually reached, from the mover's view.
    analyses = [_analyse(provider, ply.pre_fen, ply.mover) for ply in plies]
    # The position the last move left behind is searched only when play could
    # still have continued there; a finished game is scored by the rules instead.
    tail: AnalysisResult | None = None
    if not final_board.is_game_over():
        tail = _analyse(provider, final_board.fen(), final_board.turn)

    entries: list[dict] = []
    graph: list[dict] = []  # eval after each ply, from WHITE's perspective
    counts: dict[str, int] = {q.value: 0 for q in MoveQuality}
    loss_by_color: dict[str, list[int]] = {"w": [], "b": []}
    improvements: list[dict] = []

    for index, ply in enumerate(plies):
        lines = analyses[index].lines
        best = lines[0] if lines else None
        position_value = _position_value(index, plies, analyses, tail, final_board)
        played_cp, played_mate, is_best = _line_score(lines, ply.move.uci(), position_value)
        top_cp = best.score_cp if best else 0
        top_mate = best.mate_in if best else None
        loss = centipawn_loss(top_cp, played_cp, top_mate, played_mate)
        quality = classify_move(
            loss,
            is_best,
            MoveContext(
                is_forced=ply.is_forced,
                captures_value_cp=ply.captures_value_cp,
                was_checked=ply.was_checked,
            ),
        )
        explanation = explain_move(
            ply.pre_fen,
            ply.move,
            quality.value,
            loss,
            played_cp,
            best.move if best else "",
            is_best,
        )

        color = "w" if ply.mover == chess.WHITE else "b"
        entries.append(
            {
                "ply": index + 1,
                "move_number": ply.move_number,
                "uci": ply.uci,
                "san": ply.san,
                # Position the move was played from: lets the review page put a
                # board on any ply without re-deriving the replay client-side.
                "pre_fen": ply.pre_fen,
                "color": color,
                "quality": quality.value,
                "centipawn_loss": loss,
                "best_uci": best.move if best else "",
                "eval_cp": played_cp,
                "eval_mate": played_mate,
                "explanation": explanation,
            }
        )
        counts[quality.value] += 1
        loss_by_color[color].append(loss)
        graph.append(
            {
                "ply": index + 1,
                "cp": played_cp if ply.mover == chess.WHITE else -played_cp,
                "mate": played_mate,
            }
        )
        if quality in (MoveQuality.MISTAKE, MoveQuality.BLUNDER) and best is not None:
            improvements.append(
                {
                    "ply": index + 1,
                    "san": ply.san,
                    "color": color,
                    "best_uci": best.move,
                    "loss_cp": loss,
                }
            )

    return {
        "moves": entries,
        "eval_graph": graph,
        "counts": counts,
        "improvements": improvements,
        "summary": {
            "ply_count": len(entries),
            "accuracy": {"w": _accuracy(loss_by_color["w"]), "b": _accuracy(loss_by_color["b"])},
        },
    }


def generate_or_get(db: Session, game_id: int, user_id: int, *, force: bool = False) -> GameReview:
    """The review endpoint kernel: cached read, else full engine analysis.

    RB-002: everything the session must read (ownership, moves, replay
    validation) happens while connected, then ``db.commit()`` releases the
    pooled connection for the seconds-long engine batch, and one short write
    transaction persists the finished payload. A ~12 s held connection per
    review becomes ~50 ms held plus the search on plain scalars.
    """
    game = load_game(db, game_id, user_id)
    if game.status == GameStatus.ACTIVE.value:
        raise ReviewTargetError("The game is still in progress")
    stored = get_existing(db, game_id, user_id)
    if stored is not None and not force:
        return stored

    repo_moves = _game_moves(db, game_id)
    if not repo_moves:
        raise ReviewTargetError("There are no moves to review")

    # Replay + validate while still connected (a bad stored move raises before
    # the commit below, so nothing is half-written), and resolve every ORM-derived
    # scalar up front — the objects go expired at the commit.
    plies, final_board = _replay(repo_moves)
    hero_color = hero_color_for(game, user_id)
    db.commit()

    payload: dict = {}
    provider_name = "stockfish"
    status = "failed"
    error: str | None = None
    try:
        # One engine for the whole pass (ANL-003): starting a local Stockfish
        # costs a handshake plus an NNUE load, which used to be paid once per
        # position — the slowest endpoint in the app got its name that way. The
        # factory picks the binary or the hosted engine from settings, so a
        # host without a binary reviews with the key it has instead of failing.
        # MON-003: the histogram times the whole batch per provider — this is
        # the app's slowest surface and the one TD-013/ANL-008 sizing depends on.
        with open_stockfish_provider(for_review=True) as provider, engine_timer(provider.name):
            payload = analyse_plies(provider, plies, final_board)
        provider_name = provider.name
        status = "completed"
    except (EngineUnavailableError, StockfishUnavailableError) as exc:
        # MON-004: a stored failure is invisible to HTTP (the endpoint answers
        # 200 with status=failed), so the counter is the only sign of an outage.
        record_engine_unavailable()
        error = str(exc)

    # Short write transaction: build the row from the plain scalars only, so
    # no expired ORM object is read back into the connection window we just
    # closed. One row per (game, user): a forced re-analysis updates the stored
    # row in place rather than violating the unique constraint.
    review = stored if stored is not None else GameReview(game_id=game_id, user_id=user_id)
    review.provider = provider_name
    review.hero_color = hero_color
    review.depth = REVIEW_DEPTH
    review.status = status
    review.error = error
    review.payload = payload if status == "completed" else {}
    db.add(review)
    db.commit()
    db.refresh(review)
    # Project the finished analysis into the coach index so cross-game recall
    # ("what do I keep doing wrong") sees it. Best-effort: an index failure can
    # never fail the review the player asked for (Phase 11).
    if review.status == "completed":
        index_review_safe(db, review)
    return review
