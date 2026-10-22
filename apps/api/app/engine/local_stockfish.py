"""Local Stockfish provider (Phase 2).

For non-Docker development — a machine with a Homebrew/apt Stockfish binary on
PATH or at ``settings.stockfish_path``. It reuses the existing
:class:`app.engine.stockfish.StockfishProvider` adapter and maps a difficulty
level onto that adapter's bounded search, then flattens the top principal
variation into an :class:`EngineResult` so the service sees one move shape
regardless of backend.

Stockfish's own availability errors are translated to
:class:`EngineUnavailableError` so the circuit breaker treats a missing binary
exactly like a downed sidecar and falls back to the custom engine.
"""

from __future__ import annotations

import chess

from app.engine.domain import EngineDifficulty, EngineResult, budget_for
from app.engine.errors import EngineUnavailableError
from app.engine.provider import AnalyseRequest, AnalysisResult
from app.engine.stockfish import (
    StockfishConfig,
    StockfishError,
    StockfishProvider,
    StockfishUnavailableError,
)
from app.games.domain import Color


def _color_to_move(fen: str) -> Color:
    return Color.WHITE if chess.Board(fen).turn == chess.WHITE else Color.BLACK


class LocalStockfishProvider:
    """Provider that runs a locally installed Stockfish binary."""

    name = "stockfish-local"

    def __init__(self, config: StockfishConfig | None = None) -> None:
        self._provider = StockfishProvider(config or StockfishConfig())

    def move_for(self, fen: str, *, level: EngineDifficulty) -> EngineResult:
        """Ask local Stockfish for the best move within the level budget."""
        result = self._run(fen, level)
        best = result.best
        if best is None or not best.move:
            raise EngineUnavailableError("Local Stockfish returned no move")
        return EngineResult(
            best_move=best.move,
            score=best.score_cp,
            depth=result.depth,
            nodes_searched=result.nodes_searched,
            time_ms=result.time_ms,
            termination="completed",
        )

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        """Delegate review analysis to the Stockfish adapter."""
        try:
            return self._provider.analyse(request)
        except (StockfishUnavailableError, StockfishError) as exc:
            raise EngineUnavailableError(str(exc)) from exc

    def _run(self, fen: str, level: EngineDifficulty) -> AnalysisResult:
        budget = budget_for(level)
        request = AnalyseRequest(
            fen=fen,
            depth=budget.max_depth,
            multipv=1,
            max_time_ms=budget.max_time_ms,
            for_color=_color_to_move(fen),
        )
        try:
            return self._provider.analyse(request)
        except (StockfishUnavailableError, StockfishError) as exc:
            raise EngineUnavailableError(str(exc)) from exc
