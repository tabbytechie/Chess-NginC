"""Engine provider interface (Phase 9, ANL-001).

Pluggable analysis seam: Stockfish supplies chess facts (evals, best lines,
MultiPV); the custom engine supplies fast local analysis. Classification and
coaching consume the structured result — never raw engine output.

Per architecture: providers do search/evaluation only. No HTTP, no DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.engine.domain import EngineDifficulty, EngineResult
from app.games.domain import Color


@dataclass(frozen=True)
class PrincipalVariation:
    """One engine line: move, score, and the continuation (UCI moves)."""

    move: str  # UCI of the first move in this line
    score_cp: int  # centipawns from the side-to-move's perspective
    mate_in: int | None = None  # moves to mate (signed: + favors mover)
    pv: tuple[str, ...] = ()  # full principal variation in UCI


@dataclass(frozen=True)
class AnalysisResult:
    """Structured analysis of one position (the engine truth layer)."""

    fen: str
    lines: tuple[PrincipalVariation, ...] = ()
    depth: int = 0
    nodes_searched: int = 0
    time_ms: int = 0
    provider: str = "unknown"

    @property
    def best(self) -> PrincipalVariation | None:
        """Return the top line, or None when no lines were produced."""
        return self.lines[0] if self.lines else None


@dataclass(frozen=True)
class AnalyseRequest:
    """Bounded request for position analysis."""

    fen: str
    depth: int = 15
    multipv: int = 3
    max_time_ms: int = 1000
    for_color: Color = Color.WHITE
    extra: dict[str, str] = field(default_factory=dict)


class EngineProvider(Protocol):
    """Pluggable engine backend (ANL-001).

    One seam for both jobs: play (``move_for``) and review (``analyse``). The
    game service only ever depends on this protocol, never on Stockfish, the
    sidecar, or the custom engine directly.
    """

    @property
    def name(self) -> str:
        """Stable identifier for the backend (provenance and logging)."""
        ...

    def move_for(self, fen: str, *, level: EngineDifficulty) -> EngineResult:
        """Return a bounded best move for the side to move in ``fen``.

        ``level`` maps to a server-side search budget; the concrete backend
        still clamps it to its own hard bounds. Raises
        :class:`app.engine.errors.EngineUnavailableError` when the backend
        cannot produce a move so the caller can fall back.
        """
        ...

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        """Analyse a position, returning ranked principal variations."""
        ...
