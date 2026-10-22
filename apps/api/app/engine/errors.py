"""Engine provider errors (Phase 2).

These live at the provider seam so callers (the game service) depend on the
abstraction, never on a concrete backend's exception type.

* :class:`EngineUnavailableError` — the backend (typically the Stockfish
  sidecar) is unreachable, timed out, or returned 5xx. The circuit breaker turns
  this into a graceful fallback to the custom engine.
* :class:`EngineSaturatedError` — every engine slot is busy; surfaces as a 503
  with ``Retry-After`` rather than queueing an unbounded number of searches.
"""


class EngineUnavailableError(Exception):
    """The configured engine backend could not produce a move."""


class EngineSaturatedError(Exception):
    """All engine concurrency slots are busy (mapped to 503)."""
