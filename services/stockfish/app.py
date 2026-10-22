"""Stockfish sidecar — the only place the Stockfish binary runs (Phase 2).

Deliberately tiny and self-contained: it imports nothing from ``app.*`` and never
touches the database, so the API image stays binary-free and Stockfish's GPL-3.0
stays isolated in this one container (REL-011 / ADR-006). It is reachable only on
a private Docker network and has no authentication — network isolation is the
access control, and the API is the only intended caller.

Design:
* One **warm pool** of persistent UCI processes (``MAX_CONCURRENT_SEARCHES``),
  opened at boot and reused across requests. This is the ``ANL-003`` pool the
  in-API docstrings promised, and it removes the old process-per-call cost.
* Every request's ``depth``/``time_ms``/``multipv`` is re-bounded **server-side**,
  so a hostile or buggy client can never request an unbounded search.
* Searches take a pooled engine (bounded, with a short timeout); saturation is a
  503, never a hang.
"""

from __future__ import annotations

import contextlib
import os
import queue
from collections.abc import Iterator
from typing import Any

import chess
import chess.engine
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# --- Configuration (env only; the API never sends a binary path) ---
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
MAX_CONCURRENT_SEARCHES = int(os.environ.get("MAX_CONCURRENT_SEARCHES", "4"))
ENGINE_THREADS = int(os.environ.get("ENGINE_THREADS", "1"))
ENGINE_HASH_MB = int(os.environ.get("ENGINE_HASH_MB", "64"))
ACQUIRE_TIMEOUT_S = float(os.environ.get("ACQUIRE_TIMEOUT_S", "8"))

# --- Hard bounds, mirrored from the API adapter, re-applied server-side ---
MAX_DEPTH = 15
MAX_TIME_MS = 1000
MAX_MULTIPV = 5

_POOL: queue.Queue[chess.engine.SimpleEngine] = queue.Queue()
_ENGINE_ALIVE = False


class MoveRequest(BaseModel):
    fen: str
    depth: int = Field(default=6, ge=1)
    time_ms: int = Field(default=500, ge=1)
    multipv: int = Field(default=1, ge=1)


class AnalyseRequest(MoveRequest):
    pass


@contextlib.contextmanager
def _engine() -> Iterator[chess.engine.SimpleEngine]:
    """Check out a pooled engine or fail fast with a 503 when saturated."""
    try:
        engine = _POOL.get(block=True, timeout=ACQUIRE_TIMEOUT_S)
    except queue.Empty as exc:
        raise HTTPException(
            status_code=503,
            detail="Engine pool saturated",
            headers={"Retry-After": "2"},
        ) from exc
    try:
        yield engine
    finally:
        _POOL.put(engine)


def _clamp(depth: int, time_ms: int, multipv: int) -> tuple[int, int, int]:
    return (
        max(1, min(depth, MAX_DEPTH)),
        max(1, min(time_ms, MAX_TIME_MS)),
        max(1, min(multipv, MAX_MULTIPV)),
    )


def _board(fen: str) -> chess.Board:
    try:
        return chess.Board(fen)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid FEN: {exc}") from exc


def _score_parts(score: chess.engine.PovScore | None, board: chess.Board) -> tuple[int, int | None]:
    """Centipawns + mate-in from the side-to-move's perspective."""
    if score is None:
        return 0, None
    pov = score.pov(board.turn)
    if pov.is_mate():
        mate = pov.mate()
        if mate is None:
            return 0, None
        magnitude = 20000 - abs(mate) * 10
        return (magnitude if mate > 0 else -magnitude), mate
    raw = pov.score()
    return (int(raw) if raw is not None else 0), None


def _search(engine: chess.engine.SimpleEngine, board: chess.Board, depth: int, time_ms: int,
            multipv: int) -> dict[str, Any]:
    """Run one bounded MultiPV search and shape the result for the API client."""
    with contextlib.suppress(chess.engine.EngineError):
        engine.configure({"MultiPV": multipv, "Threads": ENGINE_THREADS, "Hash": ENGINE_HASH_MB})
    limit = chess.engine.Limit(depth=depth, time=time_ms / 1000.0)
    try:
        infos = engine.analyse(board, limit, multipv=multipv)
    except chess.engine.EngineError as exc:
        raise HTTPException(status_code=503, detail=f"Engine error: {exc}") from exc
    if isinstance(infos, dict):
        infos = [infos]
    dict_infos = [info for info in infos if isinstance(info, dict)]

    lines: list[dict[str, Any]] = []
    best_move = ""
    for info in dict_infos:
        pv_moves = info.get("pv") or []
        move = pv_moves[0].uci() if pv_moves else ""
        cp, mate_in = _score_parts(info.get("score"), board)
        lines.append(
            {
                "move": move,
                "score_cp": cp,
                "mate_in": mate_in,
                "pv": [m.uci() for m in pv_moves],
            }
        )
        if not best_move and move:
            best_move = move

    achieved = max((int(i.get("depth", depth)) for i in dict_infos), default=depth)
    nodes = max((int(i.get("nodes", 0)) for i in dict_infos), default=0)
    elapsed = max((int(i.get("time", 0) * 1000) for i in dict_infos), default=0)
    return {
        "move": best_move,
        "lines": lines,
        "depth": achieved,
        "nodes": nodes,
        "time_ms": elapsed,
        "provider": "stockfish",
    }


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> Iterator[None]:
    """Open the warm engine pool at boot and retire it on shutdown."""
    global _ENGINE_ALIVE
    engines: list[chess.engine.SimpleEngine] = []
    try:
        for _ in range(MAX_CONCURRENT_SEARCHES):
            engines.append(chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH))
    except Exception:  # noqa: BLE001 - boot failure must be fatal and explicit
        for engine in engines:
            with contextlib.suppress(Exception):
                engine.quit()
        raise
    # Configure once per engine; MultiPV is set per request.
    for engine in engines:
        with contextlib.suppress(chess.engine.EngineError):
            engine.configure({"Threads": ENGINE_THREADS, "Hash": ENGINE_HASH_MB})
        _POOL.put(engine)
    _ENGINE_ALIVE = True
    app.state.healthy = True
    try:
        yield
    finally:
        _ENGINE_ALIVE = False
        app.state.healthy = False
        while not _POOL.empty():
            with contextlib.suppress(queue.Empty):
                engine = _POOL.get_nowait()
                with contextlib.suppress(Exception):
                    engine.quit()
        # Quit any engine still held by an in-flight request's reference list.
        for engine in engines:
            with contextlib.suppress(Exception):
                engine.quit()


app = FastAPI(title="Stockfish sidecar", version="0.1.0", lifespan=lifespan)
app.state.healthy = False


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the engine pool booted and is considered alive."""
    if not _ENGINE_ALIVE:
        raise HTTPException(status_code=503, detail="Engine pool not ready")
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    """Readiness: at least one pooled engine is currently free."""
    if not _ENGINE_ALIVE:
        raise HTTPException(status_code=503, detail="Engine pool not ready")
    return {"status": "ok", "free_slots": _POOL.qsize()}


@app.post("/v1/move")
def move(request: MoveRequest) -> dict[str, Any]:
    """Return the best move (and requested lines) for a bounded search."""
    board = _board(request.fen)
    if board.is_game_over():
        return {"move": "", "lines": [], "depth": 0, "nodes": 0, "time_ms": 0, "provider": "stockfish"}
    depth, time_ms, multipv = _clamp(request.depth, request.time_ms, request.multipv)
    with _engine() as engine:
        return _search(engine, board, depth, time_ms, multipv)


@app.post("/v1/analyse")
def analyse(request: AnalyseRequest) -> dict[str, Any]:
    """Return ranked principal variations for review (same bounds as play)."""
    board = _board(request.fen)
    depth, time_ms, multipv = _clamp(request.depth, request.time_ms, request.multipv)
    if board.is_game_over():
        return {"fen": request.fen, "lines": [], "depth": 0, "nodes": 0, "time_ms": 0,
                "provider": "stockfish"}
    with _engine() as engine:
        result = _search(engine, board, depth, time_ms, multipv)
    result["fen"] = request.fen
    return result
