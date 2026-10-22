"""Benchmark harness: run custom engine vs reference on identical positions.

BEN-010..013: identical positions, recorded config/hardware, recorded
move/score/depth/nodes/time, normalized mate scores. The harness itself is pure;
:func:`run_suite` aggregates a versioned suite and :func:`record_run` is the
BEN-019 writer that persists provenance (provider name, version, bounds, host)
through the engine seam into ``benchmark_runs`` / ``benchmark_results``.
"""

from __future__ import annotations

import argparse
import platform
import time
from dataclasses import dataclass

import chess
from sqlalchemy.orm import Session

from app.engine.benchmark_suite import BENCHMARK_SUITE_VERSION, get_suite
from app.engine.domain import EngineConfig
from app.engine.engine import ChessEngine
from app.engine.stockfish import (
    STOCKFISH_APT_PACKAGE,
    STOCKFISH_APT_VERSION,
    StockfishConfig,
    StockfishError,
    StockfishUnavailableError,
    analyse_position,
)
from app.games.domain import Color
from app.models.benchmark_result import BenchmarkResult
from app.models.benchmark_run import BenchmarkRun


@dataclass(frozen=True)
class PositionComparison:
    """One position analysed by both engines (BEN-010/BEN-012)."""

    fen: str
    custom_move: str
    custom_score: int
    custom_depth: int
    custom_nodes: int
    custom_time_ms: int
    reference_move: str
    reference_score: int
    reference_depth: int
    reference_nodes: int
    reference_time_ms: int
    moves_agree: bool
    score_gap_cp: int  # abs(custom - reference), normalized (BEN-013)


@dataclass(frozen=True)
class BenchmarkRunResult:
    """Aggregate of one suite execution."""

    suite_version: str
    comparisons: tuple[PositionComparison, ...]
    hardware: str
    stockfish_version: str


def hardware_fingerprint() -> str:
    """Record config & hardware for repeatability (BEN-011)."""
    uname = platform.uname()
    return f"{uname.system} {uname.release} {uname.machine} | py={platform.python_version()}"


def stockfish_version_label() -> str:
    """Record Stockfish version & provenance (BEN-002/BEN-011)."""
    return f"{STOCKFISH_APT_PACKAGE} {STOCKFISH_APT_VERSION}"


def compare_position(
    fen: str,
    custom_config: EngineConfig | None = None,
    reference_config: StockfishConfig | None = None,
) -> PositionComparison:
    """Run both engines on one identical position (BEN-010)."""
    custom_cfg = custom_config or EngineConfig()
    board = chess.Board(fen)
    for_color = Color.WHITE if board.turn == chess.WHITE else Color.BLACK

    t0 = time.time()
    custom = ChessEngine(custom_cfg).search(board, for_color)
    custom_elapsed = int((time.time() - t0) * 1000)

    try:
        ref = analyse_position(fen, for_color, reference_config)
    except (StockfishUnavailableError, StockfishError):
        # Reference unavailable: record empty reference, keep custom result.
        return PositionComparison(
            fen=fen,
            custom_move=custom.best_move,
            custom_score=custom.score,
            custom_depth=custom.depth,
            custom_nodes=custom.nodes_searched,
            custom_time_ms=custom_elapsed,
            reference_move="",
            reference_score=0,
            reference_depth=0,
            reference_nodes=0,
            reference_time_ms=0,
            moves_agree=False,
            score_gap_cp=abs(custom.score),
        )

    return PositionComparison(
        fen=fen,
        custom_move=custom.best_move,
        custom_score=custom.score,
        custom_depth=custom.depth,
        custom_nodes=custom.nodes_searched,
        custom_time_ms=custom_elapsed,
        reference_move=ref.best_move,
        reference_score=ref.score,
        reference_depth=ref.depth,
        reference_nodes=ref.nodes_searched,
        reference_time_ms=ref.time_ms,
        moves_agree=custom.best_move == ref.best_move and bool(ref.best_move),
        score_gap_cp=abs(custom.score - ref.score),
    )


def agreement_rate(comparisons: tuple[PositionComparison, ...]) -> float:
    """Fraction of positions where both engines chose the same move."""
    if not comparisons:
        return 0.0
    return sum(1 for c in comparisons if c.moves_agree) / len(comparisons)


def mean_score_gap(comparisons: tuple[PositionComparison, ...]) -> float:
    """Mean absolute score gap in centipawns (BEN-013 normalized)."""
    if not comparisons:
        return 0.0
    return sum(c.score_gap_cp for c in comparisons) / len(comparisons)


def run_suite(
    custom_config: EngineConfig | None = None,
    reference_config: StockfishConfig | None = None,
) -> BenchmarkRunResult:
    """Run every position in the versioned suite through both engines (BEN-009)."""
    comparisons = tuple(
        compare_position(fen, custom_config, reference_config) for fen, _desc in get_suite()
    )
    return BenchmarkRunResult(
        suite_version=BENCHMARK_SUITE_VERSION,
        comparisons=comparisons,
        hardware=hardware_fingerprint(),
        stockfish_version=stockfish_version_label(),
    )


def record_run(
    db: Session,
    result: BenchmarkRunResult,
    *,
    custom_config: EngineConfig,
    reference_config: StockfishConfig,
    provider_name: str = "stockfish",
    commit: bool = True,
) -> BenchmarkRun:
    """Persist one run + its per-position rows (BEN-019).

    Provenance is captured in the existing columns — no schema change: the
    reference backend's *name and version* share ``stockfish_version``, the
    *bounds* live in the custom/reference depth/time columns, and the *host* in
    ``hardware``. ``provider_name`` is the seam identity that produced the
    reference moves, so a future backend swap is traceable from the data.
    """
    run = BenchmarkRun(
        suite_version=result.suite_version,
        custom_depth=custom_config.max_depth,
        custom_time_ms=custom_config.max_time_ms,
        stockfish_depth=reference_config.max_depth,
        stockfish_time_ms=reference_config.max_time_ms,
        stockfish_version=f"{provider_name} / {result.stockfish_version}",
        hardware=result.hardware,
    )
    db.add(run)
    db.flush()  # assign run.id before referencing it from the result rows
    for comp in result.comparisons:
        db.add(
            BenchmarkResult(
                run_id=run.id,
                fen=comp.fen,
                custom_move=comp.custom_move,
                custom_score=comp.custom_score,
                custom_depth=comp.custom_depth,
                custom_nodes=comp.custom_nodes,
                custom_time_ms=comp.custom_time_ms,
                reference_move=comp.reference_move,
                reference_score=comp.reference_score,
                reference_depth=comp.reference_depth,
                moves_agree=1 if comp.moves_agree else 0,
            )
        )
    if commit:
        db.commit()
    return run


def main(argv: list[str] | None = None) -> int:
    """CLI: run the suite and print metrics; ``--record`` persists provenance."""
    parser = argparse.ArgumentParser(description="Run the benchmark suite (BEN-019)")
    parser.add_argument("--record", action="store_true", help="persist the run to the database")
    parser.add_argument("--provider", default="stockfish", help="reference backend identity")
    parser.add_argument("--depth", type=int, default=None, help="override search depth for both")
    parser.add_argument("--time-ms", dest="time_ms", type=int, default=None, help="time budget")
    args = parser.parse_args(argv)

    custom_config = EngineConfig(max_depth=args.depth or 3, max_time_ms=args.time_ms or 5000)
    reference_config = StockfishConfig(
        max_depth=args.depth or 10,
        max_time_ms=args.time_ms or 500,
    )

    result = run_suite(custom_config, reference_config)
    agreement = agreement_rate(result.comparisons)
    gap = mean_score_gap(result.comparisons)
    print(
        f"suite {result.suite_version}: {len(result.comparisons)} positions, "
        f"agreement={agreement:.2f}, mean_gap={gap:.1f}cp"
    )

    if args.record:
        # Import here so the pure harness (and its tests) need no DB at import.
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            run = record_run(
                db,
                result,
                custom_config=custom_config,
                reference_config=reference_config,
                provider_name=args.provider,
            )
            print(f"recorded benchmark run id={run.id}")
        finally:
            db.close()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
