"""Chess domain types: game modes, status, and the game/move models.

These types are deliberately independent of python-chess. The rules adapter
(:mod:`app.games.rules`) is the only module that imports the ``chess`` library.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

# Standard chess starting position (FEN). Cross-checked against python-chess in tests.
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class GameMode(StrEnum):
    """Who plays the moves."""

    LOCAL = "local"  # two players on the same device
    COMPUTER = "computer"  # human vs. engine


class Color(StrEnum):
    """Side to move or piece color."""

    WHITE = "white"
    BLACK = "black"


class GameStatus(StrEnum):
    """Lifecycle state of a game."""

    ACTIVE = "active"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    DRAW = "draw"
    RESIGNED = "resigned"
    ABANDONED = "abandoned"


class EngineLevel(StrEnum):
    """Bot difficulty stored on the game row (ADR-010 maps these to budgets)."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class EndReason(StrEnum):
    """Why a game reached a terminal status. ``NULL`` while the game is active."""

    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    DRAW = "draw"
    RESIGNATION = "resignation"
    ABANDONED = "abandoned"


class GameResult(StrEnum):
    """Standard PGN result tokens."""

    WHITE_WIN = "1-0"
    BLACK_WIN = "0-1"
    DRAW = "1/2-1/2"
    OPEN = "*"


@dataclass(frozen=True)
class Move:
    """A single move in both UCI and SAN notation."""

    uci: str
    san: str


@dataclass
class Game:
    """A chess game's domain state, with no persistence concerns."""

    id: UUID = field(default_factory=uuid4)
    mode: GameMode = GameMode.LOCAL
    status: GameStatus = GameStatus.ACTIVE
    fen: str = STARTING_FEN
    moves: list[Move] = field(default_factory=list)
    player_color: Color = Color.WHITE
    result: GameResult = GameResult.OPEN

    def resign(self) -> None:
        """Mark the game as resigned by the current player."""
        if self.status != GameStatus.ACTIVE:
            raise ValueError(f"Cannot resign a game in {self.status} status")
        self.status = GameStatus.RESIGNED

    def to_pgn(self, *, utc_date: str | None = None) -> str:
        """Render the game as a standards-following PGN document.

        White is the player's opponent when the player takes Black, so the
        ``White``/``Black`` tags stay in board order while ``player_color``
        decides which side the human occupies.
        """
        return format_pgn(
            [move.san for move in self.moves],
            result=self.result.value,
            white_name="Player" if self.player_color == Color.WHITE else "Engine",
            black_name="Player" if self.player_color == Color.BLACK else "Engine",
            utc_date=utc_date,
        )


def format_pgn(
    sans: list[str],
    *,
    result: str,
    white_name: str = "White",
    black_name: str = "Black",
    start_fen: str = STARTING_FEN,
    event: str = "Chess NginC game",
    utc_date: str | None = None,
) -> str:
    """Build a standards-following PGN document from an ordered SAN ply list.

    The stored history is authoritative: plies alternate White, Black, White,
    ... starting from ``start_fen`` (every persisted game begins with White to
    move), so move numbers derive purely from position in the list. A
    non-standard start carries ``FEN``/``SetUp`` headers so the document replays.
    """
    date = utc_date or datetime.now(UTC).strftime("%Y.%m.%d")
    headers = [
        ("Event", event),
        ("Site", "chess-nginc"),
        ("Date", date),
        ("Round", "1"),
        ("White", white_name),
        ("Black", black_name),
        ("Result", result),
    ]
    if start_fen != STARTING_FEN:
        headers += [("SetUp", "1"), ("FEN", start_fen)]

    tag_section = "\n".join(f'[{key}] "{value}"' for key, value in headers)

    movetext: list[str] = []
    for index, san in enumerate(sans):
        ply = index + 1
        if ply % 2 == 1:  # White opens the full move: "1. e4"
            movetext.append(f"{ply // 2 + 1}. {san}")
        else:  # Black appends bare SAN: "... e5"
            movetext.append(san)
    body = " ".join([*movetext, result]).strip()
    return f"{tag_section}\n\n{body}\n"
