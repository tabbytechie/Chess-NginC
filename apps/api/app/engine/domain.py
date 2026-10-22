"""Chess engine domain types: configuration, results, and evaluation."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal


class EngineDifficulty(IntEnum):
    """Engine strength levels (higher = stronger)."""

    EASY = 1
    MEDIUM = 3
    HARD = 5


@dataclass(frozen=True)
class SearchBudget:
    """A bounded search budget derived from a difficulty level.

    The difficulty-to-budget map is the single place a game's ``engine_level``
    becomes concrete search work. Sidecars and adapters still clamp these values
    to their own hard bounds, so a high level can never request an unbounded
    search — see ``STOCKFISH_MAX_DEPTH`` / ``STOCKFISH_MAX_TIME_MS``.
    """

    max_depth: int
    max_time_ms: int


# Server-side difficulty budgets (ADR-010). Deliberately below the Stockfish
# hard bounds so a request always fits inside what the sidecar will honor.
_DIFFICULTY_BUDGETS: dict[EngineDifficulty, SearchBudget] = {
    EngineDifficulty.EASY: SearchBudget(max_depth=2, max_time_ms=300),
    EngineDifficulty.MEDIUM: SearchBudget(max_depth=6, max_time_ms=700),
    EngineDifficulty.HARD: SearchBudget(max_depth=12, max_time_ms=1500),
}


def budget_for(level: EngineDifficulty) -> SearchBudget:
    """Map a difficulty level to its bounded search budget."""
    return _DIFFICULTY_BUDGETS.get(level, _DIFFICULTY_BUDGETS[EngineDifficulty.MEDIUM])


# Maps the ``games.engine_level`` string to a concrete search difficulty. Kept
# here (not in the games layer) so the engine seam owns its own vocabulary.
_LEVEL_TO_DIFFICULTY: dict[str, EngineDifficulty] = {
    "easy": EngineDifficulty.EASY,
    "medium": EngineDifficulty.MEDIUM,
    "hard": EngineDifficulty.HARD,
}


def difficulty_from_level(level: str) -> EngineDifficulty:
    """Resolve a stored difficulty string, defaulting to ``MEDIUM`` when unknown."""
    return _LEVEL_TO_DIFFICULTY.get(level, EngineDifficulty.MEDIUM)


@dataclass(frozen=True)
class EngineConfig:
    """Configuration for the chess engine."""

    difficulty: EngineDifficulty = EngineDifficulty.MEDIUM
    max_depth: int = 3
    max_time_ms: int = 5000  # 5 second default


@dataclass(frozen=True)
class EngineResult:
    """Result of an engine search."""

    best_move: str  # UCI notation
    score: int  # Centipawns (positive = good for current side)
    depth: int
    nodes_searched: int
    time_ms: int
    termination: Literal["completed", "timeout", "cancelled"]
