"""BenchmarkResult model: per-position comparison (BEN-010..013, BEN-019)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class BenchmarkResult(Base):
    """One position comparison between the custom engine and Stockfish."""

    __tablename__ = "benchmark_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False, index=True)
    fen: Mapped[str] = mapped_column(Text, nullable=False)
    custom_move: Mapped[str] = mapped_column(String(10), nullable=False)
    custom_score: Mapped[int] = mapped_column(Integer, nullable=False)
    custom_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    custom_nodes: Mapped[int] = mapped_column(Integer, nullable=False)
    custom_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_move: Mapped[str] = mapped_column(String(10), nullable=False)
    reference_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    moves_agree: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
