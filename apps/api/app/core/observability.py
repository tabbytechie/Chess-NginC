"""Observability: structured JSON logs and per-request correlation ids (REL-008).

A single JSON formatter makes the "structured logs" claim in the deployment docs
true, and a request id ties every log line from one HTTP request together. The
formatter is deliberately conservative about secrets: the standard record fields
are emitted, and nothing is added that could carry a token or password.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

# The active request id, set by the middleware for the duration of a request.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Record attributes that are internal to the formatter or unsafe to emit.
_RESERVED = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
    }
)


class JsonLogFormatter(logging.Formatter):
    """Render each record as a single JSON object on stdout."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Surface any extra fields attached via `logger.info(..., extra={...})`,
        # but never the reserved LogRecord attributes.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload.setdefault(key, value)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON handler on the root logger (idempotent)."""
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def new_request_id() -> str:
    """A fresh opaque id (8 hex chars is enough to correlate, not to identify)."""
    return uuid.uuid4().hex[:8]
