"""Phase 13 Stage 13A robustness tests: pool geometry (RB-001), trusted-proxy
client IP (RB-004), preflight logging (RB-003). The review-path slices
(RB-002/RB-005) ride test_reviews.py next to the pipeline they protect."""

import ipaddress
import json
import logging

import pytest
from fastapi import Request
from starlette.types import Scope

from app.api.v1.deps import client_ip
from app.core import database
from app.core.database import settings
from app.core.telemetry import JsonFormatter


class TestPoolGeometry:
    """RB-001: the pool must carry explicit, settings-driven choices."""

    def test_create_engine_uses_the_configured_pool(self) -> None:
        pool = database.engine.pool
        assert pool.size() == settings.db_pool_size
        assert pool._max_overflow == settings.db_max_overflow
        assert database.engine.pool._pre_ping is True
        assert database.engine.pool._recycle == settings.db_pool_recycle

    def test_defaults_fit_the_single_replica_budget(self) -> None:
        # A fresh Settings() (the shipped defaults) must not exceed a sane
        # per-process envelope: 5 kept + 5 spilled = 10 < Postgres' 100.
        fresh = type(settings)()
        assert fresh.db_pool_size + fresh.db_max_overflow <= 10
        assert 0 < fresh.db_pool_recycle <= 600


def _request(peer: str, headers: list[tuple[bytes, bytes]]) -> Request:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (peer, 12345),
        "query_string": b"",
        "scheme": "http",
        "server": ("test", 80),
    }
    return Request(scope)


class TestClientIp:
    """RB-004 (TD-021): the limiter key behind a proxy, and its spoof guards."""

    def test_off_by_default_reads_the_direct_peer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert settings.trust_proxy_headers is False
        request = _request("203.0.113.9", [(b"x-forwarded-for", b"198.51.100.1")])
        assert client_ip(request) == "203.0.113.9"

    def test_trusted_peer_takes_the_rightmost_non_proxy_hop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # nginx appends the real client as the last hop, so the rightmost
        # non-proxy value is who actually connected.
        monkeypatch.setattr(settings, "trust_proxy_headers", True)
        monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8")
        request = _request("10.0.0.5", [(b"x-forwarded-for", b"198.51.100.1, 7.7.7.7")])
        assert client_ip(request) == "7.7.7.7"

    def test_trusted_peer_ignores_a_forged_leftmost_hop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The attack the shipped nginx (`$proxy_add_x_forwarded_for`) enables:
        # a client prepends a value; the real client is the appended last hop.
        # A leftmost read would honor the forgery and mint unlimited buckets.
        monkeypatch.setattr(settings, "trust_proxy_headers", True)
        monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8")
        request = _request("10.0.0.5", [(b"x-forwarded-for", b"1.2.3.4, 203.0.113.7")])
        assert client_ip(request) == "203.0.113.7"

    def test_trusted_peer_walks_past_an_inner_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A trusted CDN hop is skipped; the client is the first non-proxy left.
        monkeypatch.setattr(settings, "trust_proxy_headers", True)
        monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8, 198.51.100.0/24")
        request = _request("10.0.0.5", [(b"x-forwarded-for", b"203.0.113.9, 198.51.100.2")])
        assert client_ip(request) == "203.0.113.9"

    def test_untrusted_peer_ignores_the_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A direct (unproxied) client forging XFF must not get a second bucket.
        monkeypatch.setattr(settings, "trust_proxy_headers", True)
        monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8")
        request = _request("203.0.113.9", [(b"x-forwarded-for", b"198.51.100.1")])
        assert client_ip(request) == "203.0.113.9"

    def test_trusted_peer_without_a_usable_header_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "trust_proxy_headers", True)
        monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8")
        missing = _request("10.0.0.5", [])
        garbage = _request("10.0.0.5", [(b"x-forwarded-for", b"not-an-ip, also-not-an-ip")])
        assert client_ip(missing) == "10.0.0.5"
        assert client_ip(garbage) == "10.0.0.5"

    def test_multiple_cidrs_and_bad_entries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "trust_proxy_headers", True)
        monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8, bogus, ::1/128 ")
        request = _request("::1", [(b"x-forwarded-for", b"198.51.100.7")])
        assert client_ip(request) == "198.51.100.7"
        assert ipaddress.ip_address(client_ip(_request("203.0.113.9", [])))


class TestPreflightLogging:
    """RB-003 (W11): the boot line must actually carry its payload, names only."""

    def _emit(self, preflight: dict[str, object]) -> dict[str, object]:
        record = logging.LogRecord(
            name="chess-engine-api",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="preflight",
            args=(),
            exc_info=None,
        )
        record.preflight = preflight  # type: ignore[attr-defined]
        return json.loads(JsonFormatter().format(record))

    def test_payload_survives_the_json_formatter(self) -> None:
        # Without the formatter's preflight branch the fixed key set would drop
        # this and boot would log nothing but the word "preflight".
        entry = self._emit({"engine": "local", "env_files": [".env"], "voice": "browser_fallback"})
        assert entry["msg"] == "preflight"
        assert entry["preflight"] == {
            "engine": "local",
            "env_files": [".env"],
            "voice": "browser_fallback",
        }

    def test_plain_message_carries_no_secret(self) -> None:
        # QA-019: a key value must never reach the emitted line, in any form.
        entry = self._emit({"engine": "cloud", "trust_proxy_headers": False})
        assert "secret_key" not in entry
        assert "api_key" not in json.dumps(entry)
