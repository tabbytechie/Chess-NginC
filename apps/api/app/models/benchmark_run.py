"""BenchmarkRun model: one benchmark suite execution (BEN-009..012, BEN-019)."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.core.database import Base


class BenchmarkRun(Base):
    """A versioned benchmark run over a FEN suite (BEN-019)."""

    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    suite_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    custom_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    custom_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    stockfish_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    stockfish_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    stockfish_version: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    hardware: Mapped[str] = mapped_column(Text, nullable=False, default="")  # BEN-011
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
