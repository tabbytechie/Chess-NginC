"""Position evaluation for the custom search engine.

Negamax (the ``-child`` recursion in :mod:`app.engine.engine`) is only correct
if every leaf score is expressed from the point of view of the side *to move*
on that board. Two functions expose that contract cleanly:

* :func:`evaluate_side_to_move` — the search leaf. Positive means the player
  about to move is better. This is what the negamax recursion negates per ply.
* :func:`evaluate_position` — an absolute helper for callers (tests, the no-legal-
  moves root) that want a score from a chosen colour's point of view.

Both agree: ``evaluate_position(board, c)`` is ``evaluate_side_to_move(board)``
negated when ``c`` is not the side to move. The historical bug was returning a
White-fixed mate constant here while the search negated per ply, which inverted
the perspective at odd depths (the engine "declined a free queen" at depth 1/3/5).
"""

import chess

from app.games.domain import Color

# Piece values in centipawns.
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,  # King value for terminal positions
}

# Normalized mate magnitude. Kept well above any material total so a forced mate
# always dominates, and small enough that ``MATE_SCORE - ply`` still reads as a
# mate after the nearest-mate preference is subtracted.
MATE_SCORE = 20000


def evaluate_side_to_move(board: chess.Board) -> int:
    """Score the position in centipawns from the side-to-move's point of view.

    This is the negamax leaf contract: positive is good for whoever is to move.
    """
    if board.is_checkmate():
        # The side to move has been mated, so it is losing — no ``for_color``
        # adjustment and no White/Black special case.
        return -MATE_SCORE

    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    white = sum(len(board.pieces(pt, chess.WHITE)) * v for pt, v in PIECE_VALUES.items())
    black = sum(len(board.pieces(pt, chess.BLACK)) * v for pt, v in PIECE_VALUES.items())
    score = white - black
    return score if board.turn == chess.WHITE else -score


def evaluate_position(board: chess.Board, for_color: Color) -> int:
    """Evaluate a chess position in centipawns.

    Positive score = good for ``for_color``. Terminal positions are resolved from
    the side to move first (the mated side is losing) and then flipped to the
    requested colour, so the mate constant is no longer pinned to White.
    """
    stm = evaluate_side_to_move(board)
    if (board.turn == chess.WHITE) == (for_color == Color.WHITE):
        return stm
    return -stm
