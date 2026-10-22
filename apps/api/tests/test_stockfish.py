"""Tests for the analysis provider seam + Stockfish MultiPV (Phase 9, ANL-001/002/007).

Uses a fake UCI engine script so no Stockfish binary is required.
"""

import os
import stat
import sys
from pathlib import Path

import chess
import pytest

from app.engine.provider import AnalyseRequest, AnalysisResult, PrincipalVariation
from app.engine.stockfish import (
    REVIEW_MAX_DEPTH,
    REVIEW_MAX_TIME_MS,
    STOCKFISH_APT_PACKAGE,
    STOCKFISH_APT_VERSION,
    STOCKFISH_MAX_DEPTH,
    STOCKFISH_MAX_TIME_MS,
    STOCKFISH_UPSTREAM,
    STOCKFISH_UPSTREAM_REPO,
    StockfishConfig,
    StockfishProvider,
    StockfishUnavailableError,
    analyse_position,
    resolve_binary,
)
from app.games.domain import Color

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# The engine logic itself. Deliberately carries no shebang: the interpreter is
# named by a launcher written below, because a `#!` line cannot quote an
# interpreter path containing a space (`.../Chess NginC/...` splits at the
# space and the child dies with exit 127).
FAKE_UCI = """
import sys
def main():
    multipv = 1
    for line in sys.stdin:
        line = line.strip()
        if line == "uci":
            print("id name FakeStockfish")
            print("id author test")
            print("option name Threads type spin default 1 min 1 max 1")
            print("option name Hash type spin default 16 min 1 max 64")
            print("option name MultiPV type spin default 1 min 1 max 5")
            print("uciok")
        elif line == "isready":
            print("readyok")
        elif line.startswith("setoption"):
            if "multipv" in line.lower():
                try:
                    multipv = int(line.split()[-1])
                except ValueError:
                    multipv = 1
        elif line.startswith("position"):
            pass
        elif line.startswith("go"):
            infos = [
                ("e2e4", 20, ["e2e4", "e7e5"]),
                ("d2d4", 10, ["d2d4", "d7d5"]),
                ("g1f3", 5, ["g1f3", "g8f6"]),
            ]
            for i, (move, cp, pv) in enumerate(infos[:max(1, multipv)]):
                joined = " ".join(pv)
                # Written verbatim (no .format() on the template), so single
                # braces are the real f-string fields.
                line = f"info depth 1 multipv {i + 1} score cp {cp} pv {joined}"
                print(line)
            print("bestmove e2e4")
        elif line == "quit":
            return
        sys.stdout.flush()
main()
"""

# POSIX launcher. `#!/bin/sh` is space-free, and the interpreter path is quoted
# by the shell rather than by the kernel's shebang parser.
FAKE_LAUNCHER = """#!/bin/sh
exec "{python}" -u "{script}" "$@"
"""


def _fake_engine_files(tmp_path: Path) -> tuple[str, Path]:
    """Write the fake engine body and return (launcher path, body path)."""
    script = tmp_path / "fake-stockfish.py"
    script.write_text(FAKE_UCI)
    if os.name == "nt":
        # Windows cannot exec extensionless shebang scripts (WinError 193);
        # wrap in a .cmd so CreateProcess can launch it.
        launcher = tmp_path / "fake-stockfish.cmd"
        launcher.write_text(f'@"{sys.executable}" -u "{script}" %*\n')
    else:
        launcher = tmp_path / "fake-stockfish"
        launcher.write_text(FAKE_LAUNCHER.format(python=sys.executable, script=script))
        launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return str(launcher), script


@pytest.fixture()
def fake_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    launcher, _ = _fake_engine_files(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    return launcher


def test_provenance_constants_record_official_source() -> None:
    assert STOCKFISH_UPSTREAM == "https://stockfishchess.org"
    assert STOCKFISH_UPSTREAM_REPO == "https://github.com/official-stockfish/Stockfish"
    assert STOCKFISH_APT_PACKAGE == "stockfish"
    assert STOCKFISH_APT_VERSION  # recorded version string


def test_config_bounds_clamp_depth_time_threads_hash() -> None:
    cfg = StockfishConfig(max_depth=99, max_time_ms=99999, threads=8, hash_mb=9999).bounded()
    assert cfg.max_depth <= 15
    assert cfg.max_time_ms <= 1000
    assert cfg.threads == 1
    assert cfg.hash_mb <= 64


def test_config_bounds_multipv_clamped() -> None:
    assert StockfishConfig(multipv=99).bounded().multipv == 5
    assert StockfishConfig(multipv=0).bounded().multipv == 1


def test_review_bounds_deeper_than_play() -> None:
    play = StockfishConfig(max_depth=99, max_time_ms=99999).bounded()
    review = StockfishConfig(max_depth=99, max_time_ms=99999).bounded(for_review=True)
    assert REVIEW_MAX_DEPTH == 25
    assert REVIEW_MAX_TIME_MS == 5000
    assert review.max_depth == REVIEW_MAX_DEPTH
    assert review.max_time_ms == REVIEW_MAX_TIME_MS
    assert play.max_depth == STOCKFISH_MAX_DEPTH
    assert play.max_time_ms == STOCKFISH_MAX_TIME_MS


def test_missing_binary_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(StockfishUnavailableError):
        resolve_binary("")


def test_analyse_starting_position_with_fake_binary(fake_binary: str) -> None:
    # A generous budget keeps this deterministic: the timeout flag trips at
    # `elapsed_ms > max_time_ms * 2`, and a cold-starting fake interpreter can
    # exceed the 500 ms default under full-suite load without being slow.
    result = analyse_position(
        STARTING_FEN, Color.WHITE, StockfishConfig(path=fake_binary, max_time_ms=30_000)
    )
    assert result.best_move in [m.uci() for m in chess.Board(STARTING_FEN).legal_moves]
    assert result.termination == "completed"
    assert result.time_ms >= 0


def test_analyse_unavailable_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(StockfishUnavailableError):
        analyse_position(STARTING_FEN, Color.WHITE, StockfishConfig(path=""))


def test_provider_returns_ranked_multipv_lines(fake_binary: str) -> None:
    provider = StockfishProvider(StockfishConfig(path=fake_binary))
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=3))
    assert isinstance(result, AnalysisResult)
    assert result.provider == "stockfish"
    assert len(result.lines) == 3
    assert [line.move for line in result.lines] == ["e2e4", "d2d4", "g1f3"]
    assert result.lines[0].score_cp > result.lines[1].score_cp > result.lines[2].score_cp
    assert result.best is not None
    assert result.best.move == "e2e4"
    assert result.best.pv == ("e2e4", "e7e5")


def test_provider_single_line_when_multipv_one(fake_binary: str) -> None:
    provider = StockfishProvider(StockfishConfig(path=fake_binary))
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
    assert len(result.lines) == 1
    assert isinstance(result.lines[0], PrincipalVariation)


def test_provider_review_mode_uses_deeper_bounds(fake_binary: str) -> None:
    provider = StockfishProvider(StockfishConfig(path=fake_binary), for_review=True)
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=99, multipv=1))
    assert result.depth <= REVIEW_MAX_DEPTH


def test_provider_unavailable_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    provider = StockfishProvider(StockfishConfig(path=""))
    with pytest.raises(StockfishUnavailableError):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
