"""Custom-engine provider: the always-available fallback (Phase 2).

Wraps :class:`app.engine.engine.ChessEngine` behind the ``EngineProvider`` seam.
It is the degraded path when the Stockfish sidecar is down, so it must never
raise for a legal position — only for a genuinely unparsable FEN. Search depth
is clamped because the pure-Python negamax gets expensive past ~6 plies; the
difficulty time budget still bounds each call.
"""

from __future__ import annotations

import chess

from app.engine.domain import EngineConfig, EngineDifficulty, EngineResult, budget_for
from app.engine.engine import ChessEngine
from app.engine.errors import EngineUnavailableError
from app.engine.provider import AnalyseRequest, AnalysisResult, PrincipalVariation
from app.games.domain import Color

# Pure-Python negamax is O(branching^depth); clamp nominal depth so a HARD budget
# degrades to a shallower achieved depth (iterative deepening) instead of stalling.
_MAX_DEPTH = 6


def _color_to_move(board: chess.Board) -> Color:
    return Color.WHITE if board.turn == chess.WHITE else Color.BLACK


class CustomEngineProvider:
    """Provider backed by the in-process custom chess engine."""

    name = "custom"

    def move_for(self, fen: str, *, level: EngineDifficulty) -> EngineResult:
        """Search the position and return the best move within the level budget."""
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            raise EngineUnavailableError(f"Invalid FEN for custom engine: {exc}") from exc
        budget = budget_for(level)
        config = EngineConfig(
            difficulty=level,
            max_depth=min(budget.max_depth, _MAX_DEPTH),
            max_time_ms=budget.max_time_ms,
        )
        return ChessEngine(config).search(board, _color_to_move(board))

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        """Single-line analysis via the custom engine (fallback for review)."""
        try:
            board = chess.Board(request.fen)
        except ValueError as exc:
            raise EngineUnavailableError(f"Invalid FEN for custom engine: {exc}") from exc
        config = EngineConfig(
            max_depth=min(request.depth, _MAX_DEPTH),
            max_time_ms=request.max_time_ms,
        )
        result = ChessEngine(config).search(board, _color_to_move(board))
        line = PrincipalVariation(
            move=result.best_move, score_cp=result.score, pv=(result.best_move,)
        )
        return AnalysisResult(
            fen=request.fen,
            lines=(line,) if result.best_move else (),
            depth=result.depth,
            nodes_searched=result.nodes_searched,
            time_ms=result.time_ms,
            provider=self.name,
        )
