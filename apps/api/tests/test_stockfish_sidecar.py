"""Sidecar endpoint tests — run the real ``services/stockfish/app.py``.

The sidecar is a separate container that normally shells out to a Stockfish
binary. These tests stub ``popen_uci`` so the HTTP surface, the warm engine pool,
the **server-side bounds**, and the health checks are exercised without any
binary — which is what lets the "a buggy client cannot request an unbounded
search" guarantee be verified in CI.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import chess
import chess.engine
import pytest
from fastapi.testclient import TestClient

SIDECAR_PATH = Path(__file__).resolve().parents[3] / "services" / "stockfish" / "app.py"

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
CHECKMATE_FEN = "Q5k1/5ppp/8/8/8/8/8/K7 b - - 0 1"


class _StubEngine:
    """A UCI engine stand-in: echoes the requested search depth and a legal move."""

    last_limit: dict[str, Any] | None = None

    def configure(self, options: dict[str, Any]) -> None:  # noqa: D401 - stub
        self.last_options = options

    def analyse(
        self, board: chess.Board, limit: chess.engine.Limit, *, multipv: int = 1, **_: Any
    ) -> list[dict[str, Any]]:
        _StubEngine.last_limit = {
            "depth": limit.depth,
            "time": limit.time,
            "multipv": multipv,
        }
        first = next(iter(board.legal_moves), None)
        if first is None:
            return []
        infos: list[dict[str, Any]] = []
        for i in range(multipv):
            infos.append(
                {
                    "pv": [first],
                    "score": chess.engine.PovScore(chess.engine.Cp(20 - i), board.turn),
                    "depth": int(limit.depth or 1),
                    "nodes": 1000,
                    "time": 0.05,
                }
            )
        return infos

    def quit(self) -> None:
        return None


@pytest.fixture()
def sidecar_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Boot the sidecar app with a stubbed engine pool, then tear it down."""
    assert SIDECAR_PATH.exists(), f"sidecar not found at {SIDECAR_PATH}"
    monkeypatch.setenv("MAX_CONCURRENT_SEARCHES", "2")
    monkeypatch.setenv("STOCKFISH_PATH", "/nonexistent-but-never-called")

    # Patch popen_uci before the module reads nothing from it at import; lifespan
    # calls it on TestClient context entry.
    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        staticmethod(lambda path, *a, **k: _StubEngine()),
    )
    _StubEngine.last_limit = None

    spec = importlib.util.spec_from_file_location("stockfish_sidecar_app", SIDECAR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with TestClient(module.app) as client:
        yield client
    sys.modules.pop(spec.name, None)


def test_health_and_ready_after_boot(sidecar_client: TestClient) -> None:
    assert sidecar_client.get("/healthz").status_code == 200
    ready = sidecar_client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["free_slots"] == 2  # pool sized to MAX_CONCURRENT_SEARCHES


def test_move_endpoint_returns_a_legal_move(sidecar_client: TestClient) -> None:
    resp = sidecar_client.post("/v1/move", json={"fen": STARTING_FEN, "depth": 6, "multipv": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["move"] in [m.uci() for m in chess.Board(STARTING_FEN).legal_moves]
    assert body["provider"] == "stockfish"
    assert len(body["lines"]) >= 1


def test_move_endpoint_clamps_bounds_server_side(sidecar_client: TestClient) -> None:
    """A hostile client asking for depth 999 / 99999ms / multipv 99 is capped."""
    resp = sidecar_client.post(
        "/v1/move",
        json={"fen": STARTING_FEN, "depth": 999, "time_ms": 99999, "multipv": 99},
    )
    assert resp.status_code == 200
    assert resp.json()["depth"] <= 15  # achieved depth echoes the clamped limit
    limit = _StubEngine.last_limit
    assert limit is not None
    assert limit["depth"] == 15
    assert limit["multipv"] == 5


def test_analyse_endpoint_returns_ranked_lines(sidecar_client: TestClient) -> None:
    resp = sidecar_client.post("/v1/analyse", json={"fen": STARTING_FEN, "depth": 10, "multipv": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["fen"] == STARTING_FEN
    assert len(body["lines"]) == 3
    scores = [line["score_cp"] for line in body["lines"]]
    assert scores == sorted(scores, reverse=True)


def test_move_on_finished_game_returns_no_move(sidecar_client: TestClient) -> None:
    resp = sidecar_client.post("/v1/move", json={"fen": CHECKMATE_FEN})
    assert resp.status_code == 200
    assert resp.json()["move"] == ""


def test_invalid_fen_is_rejected(sidecar_client: TestClient) -> None:
    resp = sidecar_client.post("/v1/move", json={"fen": "clearly-not-a-fen"})
    assert resp.status_code == 422
