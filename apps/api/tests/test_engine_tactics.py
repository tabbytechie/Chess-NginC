"""Tactical regression suite for the engine provider seam (Phase 2).

The point of this file is the bug the assessment found: the custom engine was
*provably wrong*, not just weak — a fixed-POV mate constant combined with per-ply
negamax negation inverted the score at odd depths, so it declined a free queen at
depth 1/3/5. These cases pin the behaviour:

* The custom fallback must solve each tactic at every shipped difficulty.
* The same tactics are asserted against the Stockfish-backed providers **when a
  real engine is available** (a local binary or a reachable sidecar), so a future
  backend swap cannot silently regress. Those two are skipped automatically when
  no such engine is configured, which is the case in CI.
* The circuit breaker turns a dead sidecar into a real fallback move, never a 500.
"""

from __future__ import annotations

import dataclasses
import os

import chess
import httpx
import pytest

from app.engine.circuit import CircuitBreaker, ResilientEngineProvider, SearchLimiter
from app.engine.custom_provider import CustomEngineProvider
from app.engine.domain import EngineConfig, EngineDifficulty, EngineResult, budget_for
from app.engine.engine import ChessEngine
from app.engine.errors import EngineSaturatedError, EngineUnavailableError
from app.engine.local_stockfish import LocalStockfishProvider
from app.engine.provider import AnalyseRequest
from app.engine.remote_stockfish import RemoteStockfishProvider
from app.engine.stockfish import StockfishConfig, StockfishUnavailableError, resolve_binary
from app.games.domain import Color


@dataclasses.dataclass(frozen=True)
class Tactic:
    """One position the opponent must play correctly, with a backend-agnostic check."""

    id: str
    fen: str
    level: EngineDifficulty
    kind: str  # "mate" or "capture"
    target: str | None = None  # square captured in a "capture" tactic


TACTICS = [
    Tactic("back-rank-mate", "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", EngineDifficulty.EASY, "mate"),
    Tactic(
        "free-queen", "4k3/8/8/3q4/2P5/8/8/4K3 w - - 0 1", EngineDifficulty.EASY, "capture", "d5"
    ),
    Tactic(
        "free-rook", "4k3/8/8/2r5/3P4/8/8/4K3 w - - 0 1", EngineDifficulty.EASY, "capture", "c5"
    ),
    Tactic(
        "queen-takes-rook",
        "2r2k2/1Q6/8/8/8/8/8/4K3 w - - 0 1",
        EngineDifficulty.MEDIUM,
        "capture",
        "c8",
    ),
    Tactic(
        "free-queen-hard",
        "4k3/8/8/3q4/2P5/8/8/4K3 w - - 0 1",
        EngineDifficulty.HARD,
        "capture",
        "d5",
    ),
]


def _available_providers() -> list[tuple[str, object]]:
    """Every backend we can actually run here. Custom is always available."""
    providers: list[tuple[str, object]] = [("custom", CustomEngineProvider())]

    # Local Stockfish only when a real binary resolves (PATH or configured path).
    try:
        binary = resolve_binary(os.environ.get("STOCKFISH_PATH", ""))
        providers.append(("stockfish-local", LocalStockfishProvider(StockfishConfig(path=binary))))
    except StockfishUnavailableError:
        pass

    # Remote sidecar only when a base URL is provided and it answers /healthz.
    base = os.environ.get("SIDECAR_BASE_URL", "")
    if base:
        try:
            if httpx.get(f"{base.rstrip('/')}/healthz", timeout=2.0).status_code == 200:
                providers.append(("stockfish-remote", RemoteStockfishProvider(base)))
        except httpx.HTTPError:
            pass

    return providers


def _assert_tactic(tactic: Tactic, provider_name: str, best_move: str) -> None:
    """Verify the tactic is realized, independent of which legal move was chosen."""
    board = chess.Board(tactic.fen)
    assert best_move in [m.uci() for m in board.legal_moves], (
        f"{provider_name}: illegal move {best_move!r} in {tactic.id}"
    )
    move = chess.Move.from_uci(best_move)
    if tactic.kind == "mate":
        board.push(move)
        assert board.is_checkmate(), f"{provider_name}: {tactic.id} did not deliver mate"
    else:
        assert tactic.target is not None
        assert board.is_capture(move) and move.to_square == chess.parse_square(tactic.target), (
            f"{provider_name}: expected capture on {tactic.target}, got {best_move}"
        )


@pytest.mark.parametrize("tactic", TACTICS, ids=[t.id for t in TACTICS])
def test_all_available_backends_solve_tactics(tactic: Tactic) -> None:
    """Each runnable backend must solve each tactic at the shipped difficulty."""
    ran = 0
    for name, provider in _available_providers():
        result = provider.move_for(tactic.fen, level=tactic.level)  # type: ignore[attr-defined]
        assert result.best_move, f"{name} returned no move for {tactic.id}"
        _assert_tactic(tactic, name, result.best_move)
        ran += 1
    assert ran >= 1, "at least the custom fallback must run"


def test_custom_perspective_is_consistent_at_odd_depths() -> None:
    """The exact regression: a winning capture must score positive at 1, 3 and 5.

    Before the fix these depths inverted the sign (the engine saw itself as
    losing the queen it had just won), which is why it 'declined' free material.
    """
    fen = TACTICS[1].fen  # free-queen
    for depth in (1, 3, 5):
        result = ChessEngine(EngineConfig(max_depth=depth, max_time_ms=3000)).search(
            chess.Board(fen), Color.WHITE
        )
        assert result.best_move == "c4d5", (
            f"depth {depth} missed the free queen ({result.best_move})"
        )
        # Capturing the queen leaves White up a pawn (kings cancel), so the score
        # is positive; the pre-fix engine returned a negative sign at odd depths.
        assert result.score > 0, f"depth {depth} score {result.score} should favour White"


def test_custom_reports_achieved_depth_on_timeout() -> None:
    """A tiny budget must return the best move from a shallower depth, not fail."""
    result = ChessEngine(EngineConfig(max_depth=12, max_time_ms=1)).search(
        chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
        Color.WHITE,
    )
    assert result.best_move != ""
    assert result.best_move in [m.uci() for m in chess.Board().legal_moves]
    assert result.depth < 12  # achieved, not nominal
    assert result.termination == "timeout"


def test_difficulty_budgets_are_bounded() -> None:
    """easy/medium/hard map to increasing but always-sidecar-safe budgets."""
    easy = budget_for(EngineDifficulty.EASY)
    medium = budget_for(EngineDifficulty.MEDIUM)
    hard = budget_for(EngineDifficulty.HARD)
    assert easy.max_depth < medium.max_depth < hard.max_depth
    assert hard.max_depth <= 15  # never asks more than the sidecar hard bound
    assert hard.max_time_ms <= 1500


def test_circuit_breaker_falls_back_and_never_raises() -> None:
    """A permanently dead sidecar degrades to the custom engine, not a 500."""

    class DeadProvider:
        name = "dead"

        def move_for(self, fen: str, *, level: EngineDifficulty) -> EngineResult:
            raise EngineUnavailableError("sidecar down")

        def analyse(self, request: AnalyseRequest) -> object:
            raise EngineUnavailableError("sidecar down")

    resilient = ResilientEngineProvider(
        DeadProvider(), CustomEngineProvider(), CircuitBreaker(failure_threshold=1)
    )
    result = resilient.move_for(TACTICS[1].fen, level=EngineDifficulty.EASY)
    assert result.best_move == "c4d5", "fallback must still win the free queen"
    # Second call: the circuit is open, so the dead primary is not even tried.
    result2 = resilient.move_for(TACTICS[0].fen, level=EngineDifficulty.EASY)
    assert result2.best_move == "a1a8"


def test_search_limiter_saturates_with_engine_saturated_error() -> None:
    """Exceeding the per-user cap raises EngineSaturatedError (mapped to 503)."""
    limiter = SearchLimiter(max_concurrent=2, max_per_user=1)
    # Hold one slot for the user; a second concurrent slot for the same user must
    # raise before its body runs (the cap is per-user, not just global).
    with (
        limiter.slot(1),
        pytest.raises(EngineSaturatedError),
        limiter.slot(1),
    ):
        pass  # pragma: no cover - the inner slot raises before entering


def test_remote_provider_parses_sidecar_move() -> None:
    """RemoteStockfishProvider flattens a sidecar /v1/move body into EngineResult."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/move"
        body = request.read()
        assert b"c4d5" not in body  # client never dictates the move
        return httpx.Response(
            200,
            json={
                "move": "c4d5",
                "lines": [{"move": "c4d5", "score_cp": 900, "pv": ["c4d5"]}],
                "depth": 12,
                "nodes": 5000,
                "time_ms": 120,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://engine")
    provider = RemoteStockfishProvider("http://engine", client=client)
    result = provider.move_for(TACTICS[1].fen, level=EngineDifficulty.MEDIUM)
    assert result.best_move == "c4d5"
    assert result.score == 900
    assert result.depth == 12
    client.close()


def test_remote_provider_raises_unavailable_on_5xx() -> None:
    """A 5xx from the sidecar becomes EngineUnavailableError, feeding the breaker."""

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(502, text="bad gateway")

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://engine")
    provider = RemoteStockfishProvider("http://engine", client=client)
    with pytest.raises(EngineUnavailableError):
        provider.move_for(TACTICS[1].fen, level=EngineDifficulty.EASY)
    client.close()
