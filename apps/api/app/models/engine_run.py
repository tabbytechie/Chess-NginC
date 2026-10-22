"""EngineRun model for AI analysis."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class EngineRun(Base):
    """Engine analysis run."""

    __tablename__ = "engine_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", name="fk_engine_runs_game_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fen: Mapped[str] = mapped_column(Text, nullable=False)  # Position analyzed
    best_move: Mapped[str] = mapped_column(String(10), nullable=False)  # UCI notation
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # Centipawns
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    nodes_searched: Mapped[int] = mapped_column(Integer, nullable=False)
    time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
