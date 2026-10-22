"""Remote Stockfish provider — the API-side client for the sidecar (Phase 2).

Talks HTTP to the ``services/stockfish`` container over a private network. It is
the production opponent. Connection/read timeouts are short and fixed so a hung
sidecar fails fast into the circuit breaker (which falls back to the custom
engine) rather than stalling the request.

Any transport failure, timeout, or 5xx becomes
:class:`app.engine.errors.EngineUnavailableError`; the sidecar re-applies the
hard resource bounds server-side, so a buggy or hostile API caller still cannot
request an unbounded search.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.engine.domain import EngineDifficulty, EngineResult, budget_for
from app.engine.errors import EngineUnavailableError
from app.engine.provider import (
    AnalyseRequest,
    AnalysisResult,
    PrincipalVariation,
)

MOVE_PATH = "/v1/move"
ANALYSE_PATH = "/v1/analyse"


class RemoteStockfishProvider:
    """Provider that calls the Stockfish sidecar over HTTP."""

    name = "stockfish-remote"

    def __init__(
        self,
        base_url: str,
        *,
        connect_timeout_ms: int = 3000,
        read_timeout_ms: int = 8000,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        timeout = httpx.Timeout(
            connect=connect_timeout_ms / 1000.0,
            read=read_timeout_ms / 1000.0,
            write=connect_timeout_ms / 1000.0,
            pool=read_timeout_ms / 1000.0,
        )
        # A client may be injected for tests; otherwise we own one (persistent
        # connection pool to the sidecar) and must be able to close it.
        self._client = client or httpx.Client(base_url=self._base_url, timeout=timeout)
        self._owns_client = client is None

    def close(self) -> None:
        """Close the underlying client only if this provider created it."""
        if self._owns_client:
            self._client.close()

    def move_for(self, fen: str, *, level: EngineDifficulty) -> EngineResult:
        """Request a bounded best move from the sidecar."""
        budget = budget_for(level)
        payload = {
            "fen": fen,
            "depth": budget.max_depth,
            "time_ms": budget.max_time_ms,
            "multipv": 1,
        }
        data = self._post(MOVE_PATH, payload)
        move = str(data.get("move", ""))
        if not move:
            raise EngineUnavailableError("Sidecar returned no move")
        lines = data.get("lines") or []
        score = _score_from_lines(lines)
        return EngineResult(
            best_move=move,
            score=score,
            depth=int(data.get("depth", budget.max_depth)),
            nodes_searched=int(data.get("nodes", 0)),
            time_ms=int(data.get("time_ms", 0)),
            termination="completed",
        )

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        """Request MultiPV analysis from the sidecar."""
        payload = {
            "fen": request.fen,
            "depth": request.depth,
            "time_ms": request.max_time_ms,
            "multipv": request.multipv,
        }
        data = self._post(ANALYSE_PATH, payload)
        lines = tuple(_line_from_dict(line) for line in data.get("lines", []))
        return AnalysisResult(
            fen=request.fen,
            lines=lines,
            depth=int(data.get("depth", request.depth)),
            nodes_searched=int(data.get("nodes", 0)),
            time_ms=int(data.get("time_ms", 0)),
            provider=self.name,
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload)
        except httpx.HTTPError as exc:  # includes timeouts and connection errors
            raise EngineUnavailableError(f"Sidecar request failed: {exc}") from exc
        if response.status_code >= 500:
            raise EngineUnavailableError(f"Sidecar returned {response.status_code}")
        if response.status_code >= 400:
            raise EngineUnavailableError(f"Sidecar rejected the request: {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise EngineUnavailableError("Sidecar returned non-JSON") from exc
        if not isinstance(body, dict):
            raise EngineUnavailableError("Sidecar returned an unexpected shape")
        return body


def _score_from_lines(lines: list[dict[str, Any]]) -> int:
    """Centipawn score of the best line, from the side to move."""
    if not lines:
        return 0
    first = lines[0]
    try:
        return int(first.get("score_cp", 0))
    except (TypeError, ValueError):
        return 0


def _line_from_dict(entry: dict[str, Any]) -> PrincipalVariation:
    mate_in = entry.get("mate_in")
    return PrincipalVariation(
        move=str(entry.get("move", "")),
        score_cp=int(entry.get("score_cp", 0) or 0),
        mate_in=int(mate_in) if mate_in is not None else None,
        pv=tuple(str(m) for m in entry.get("pv", ())),
    )
