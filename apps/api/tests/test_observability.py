"""Structured logging is real (REL-008): one JSON line, correlated per request."""

import json
import logging

from app.core.observability import JsonLogFormatter, new_request_id, request_id_ctx


def _record() -> logging.LogRecord:
    return logging.LogRecord(
        name="chess-engine-api.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )


def test_formatter_emits_json_with_core_fields() -> None:
    formatter = JsonLogFormatter()
    payload = json.loads(formatter.format(_record()))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "chess-engine-api.test"
    assert payload["message"] == "hello"
    assert payload["request_id"] == "-"  # default outside a request


def test_formatter_includes_active_request_id() -> None:
    rid = new_request_id()
    token = request_id_ctx.set(rid)
    try:
        payload = json.loads(JsonLogFormatter().format(_record()))
    finally:
        request_id_ctx.reset(token)
    assert payload["request_id"] == rid


def test_formatter_carries_extra_fields_but_omits_internals() -> None:
    record = _record()
    record.path = "/api/v1/games"  # an `extra=` style field
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["path"] == "/api/v1/games"
    # Reserved LogRecord attributes are never leaked into the JSON payload.
    assert "args" not in payload
    assert "msg" not in payload
    assert "pathname" not in payload
