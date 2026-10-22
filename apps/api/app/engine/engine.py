"""Custom chess engine: negamax with alpha-beta pruning and iterative deepening.

Three correctness properties the earlier fixed-depth version lacked:

* **Perspective.** Every leaf is scored from the side to move (:func:`
  evaluate_side_to_move`), so the ``-child`` negamax recursion stays consistent.
  The old code mixed a White-fixed mate constant with per-ply negation, which
  inverted the score at odd depths.
* **Nearest-mate preference.** Mate scores carry ``- ply`` so a mate in one beats
  a mate in five from the same position.
* **Achieved depth.** Iterative deepening means a timeout still returns the best
  move from the last *fully searched* depth, and :attr:`EngineResult.depth`
  reports that achieved depth rather than the nominal budget.
"""

import time
from typing import Literal

import chess

from app.engine.domain import EngineConfig, EngineResult
from app.engine.evaluator import MATE_SCORE, evaluate_position, evaluate_side_to_move
from app.games.domain import Color


class ChessEngine:
    """A search-based chess engine with configurable depth."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()
        self._nodes_searched = 0
        self._cancelled = False
        self._deadline_ms = 0.0
        self._max_ply = 0

    def search(self, board: chess.Board, for_color: Color) -> EngineResult:
        """Search for the best move from the current position."""
        start_time = time.perf_counter()
        self._nodes_searched = 0
        self._cancelled = False
        self._deadline_ms = start_time * 1000 + self.config.max_time_ms

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            # No legal moves — game over (mate or stalemate), nothing to search.
            return EngineResult(
                best_move="",
                score=evaluate_position(board, for_color),
                depth=0,
                nodes_searched=0,
                time_ms=0,
                termination="completed",
            )

        nominal_depth = self.config.max_depth
        best_move = legal_moves[0].uci()
        best_score = 0
        achieved_depth = 0

        # Iterative deepening: search depth 1, 2, ... up to the budget. A partial
        # deeper pass is discarded, so ``best_move`` is always the best from the
        # last complete depth and ``achieved_depth`` reflects real work done.
        for depth in range(1, nominal_depth + 1):
            self._max_ply = 0
            move_at_depth, score_at_depth = self._root_search(board, depth)
            if move_at_depth is None:
                # Aborted mid-pass (cancel or timeout): keep the previous depth.
                break
            best_move = move_at_depth
            best_score = score_at_depth
            achieved_depth = depth
            if self._cancelled or self._is_timeout():
                break

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        termination: Literal["completed", "timeout", "cancelled"]
        if self._cancelled:
            termination = "cancelled"
        elif achieved_depth < nominal_depth:
            termination = "timeout"
        else:
            termination = "completed"

        return EngineResult(
            best_move=best_move,
            score=best_score,
            depth=achieved_depth,
            nodes_searched=self._nodes_searched,
            time_ms=elapsed_ms,
            termination=termination,
        )

    def _root_search(self, board: chess.Board, depth: int) -> tuple[str | None, int]:
        """One full-depth root pass. Returns (None, 0) if aborted before finishing."""
        best_move: str | None = None
        best_score = -float("inf")
        for move in board.legal_moves:
            board.push(move)
            score = -self._negamax(board, depth - 1, -float("inf"), float("inf"), ply=1)
            board.pop()

            if self._cancelled or self._is_timeout():
                return None, 0

            if score > best_score:
                best_score = score
                best_move = move.uci()

        if best_move is None:  # pragma: no cover - defensive
            return None, 0
        return best_move, int(best_score)

    def cancel(self) -> None:
        """Cancel the current search."""
        self._cancelled = True

    def _negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: float,
        beta: float,
        ply: int,
    ) -> float:
        """Negamax with alpha-beta pruning; scores are side-to-move POV."""
        self._nodes_searched += 1
        self._max_ply = max(self._max_ply, ply)

        if self._cancelled or self._is_timeout():
            return 0.0

        if board.is_checkmate():
            # Mated side to move loses; ``- ply`` makes a nearer mate score higher.
            return -(MATE_SCORE - ply)

        if depth == 0 or board.is_stalemate() or board.is_insufficient_material():
            return evaluate_side_to_move(board)

        best = -float("inf")
        for move in board.legal_moves:
            board.push(move)
            value = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()

            best = max(best, value)
            alpha = max(alpha, best)
            if alpha >= beta:
                break  # Beta cutoff

        return best

    def _is_timeout(self) -> bool:
        """Check if the search has exceeded its time limit."""
        return time.perf_counter() * 1000 > self._deadline_ms
