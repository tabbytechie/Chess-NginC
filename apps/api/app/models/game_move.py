"""GameMove model for move history."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class GameMove(Base):
    """Individual move in a game."""

    __tablename__ = "game_moves"
    __table_args__ = (
        # Two concurrent writes for the same ply must not both land: this is the
        # backstop for the `count(moves) + 1` numbering in the service layer.
        UniqueConstraint("game_id", "move_number", name="uq_game_moves_game_move_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", name="fk_game_moves_game_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uci: Mapped[str] = mapped_column(String(10), nullable=False)  # UCI notation
    san: Mapped[str] = mapped_column(String(20), nullable=False)  # SAN notation
    move_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Sequence number
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
