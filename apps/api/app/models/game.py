"""Game model for chess games."""

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base
from app.games.domain import Color, EndReason, EngineLevel, GameMode, GameResult, GameStatus


def _quoted_values(enum_cls: Iterable[StrEnum]) -> str:
    """`'a', 'b', ...` for a CHECK constraint, kept in sync with the domain enum."""
    return ", ".join(f"'{member.value}'" for member in enum_cls)


class Game(Base):
    """Chess game state."""

    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_quoted_values(GameStatus)})",
            name="ck_games_status",
        ),
        CheckConstraint(
            f"mode IN ({_quoted_values(GameMode)})",
            name="ck_games_mode",
        ),
        CheckConstraint(
            f"player_color IN ({_quoted_values(Color)})",
            name="ck_games_player_color",
        ),
        CheckConstraint(
            f"engine_level IN ({_quoted_values(EngineLevel)})",
            name="ck_games_engine_level",
        ),
        # Nullable columns: a CHECK that references a NULL value evaluates to
        # NULL (not FALSE), so active games with no result pass automatically.
        CheckConstraint(
            f"end_reason IN ({_quoted_values(EndReason)})",
            name="ck_games_end_reason",
        ),
        CheckConstraint(
            f"winner IN ({_quoted_values(Color)})",
            name="ck_games_winner",
        ),
        CheckConstraint(
            f"result IN ({_quoted_values(GameResult)})",
            name="ck_games_result",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_games_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(50), nullable=False)  # 'local' or 'computer'
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # 'active', 'checkmate', etc.
    fen: Mapped[str] = mapped_column(Text, nullable=False)
    player_color: Mapped[str] = mapped_column(
        String(5), default=Color.WHITE.value, nullable=False
    )  # the human/player side in a computer game
    engine_level: Mapped[str] = mapped_column(
        String(12), default=EngineLevel.MEDIUM.value, nullable=False
    )  # 'easy' | 'medium' | 'hard' (computer games)
    end_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    winner: Mapped[str | None] = mapped_column(String(5), nullable=True)  # 'white' | 'black'
    result: Mapped[str] = mapped_column(
        String(8), default=GameResult.OPEN.value, nullable=False
    )  # '1-0' | '0-1' | '1/2-1/2' | '*'
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )  # For optimistic concurrency
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
