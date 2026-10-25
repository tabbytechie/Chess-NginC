"""Tests for the ElevenLabs TTS proxy endpoint (app/api/v1/tts.py).

No real ElevenLabs key is required: the endpoint returns 503 when the key is
empty (the CI/dev default), and each test monkeypatches settings to simulate
the key being configured or the upstream returning an error.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.tts import reset_tts_rate_limits
from app.core.database import settings


@pytest.fixture(autouse=True)
def _clear_tts_limits() -> Generator[None, None, None]:
    reset_tts_rate_limits()
    yield
    reset_tts_rate_limits()


def _fake_response(status_code: int, content: bytes = b"", text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.text = text
    return resp


class TestTTSNotConfigured:
    """With no API key (the CI/dev default) the endpoint returns 503."""

    def test_returns_503_when_key_is_empty(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "", raising=False)
        resp = client.post("/api/v1/tts", json={"text": "Knight to f3."})
        assert resp.status_code == 503

    def test_503_detail_mentions_fallback(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "", raising=False)
        resp = client.post("/api/v1/tts", json={"text": "Knight to f3."})
        assert "fallback" in resp.json()["detail"].lower()


class TestTTSRequestValidation:
    """Pydantic validation on the request body."""

    def test_rejects_empty_text(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "fake-key", raising=False)
        resp = client.post("/api/v1/tts", json={"text": ""})
        assert resp.status_code == 422

    def test_rejects_oversized_text(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "fake-key", raising=False)
        resp = client.post("/api/v1/tts", json={"text": "x" * 501})
        assert resp.status_code == 422


class TestTTSSuccess:
    """When the upstream returns 200, the audio bytes are piped through."""

    def test_returns_audio_mp3_with_key_configured(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "fake-key", raising=False)
        monkeypatch.setattr(settings, "elevenlabs_voice_id", "pNInz6obpgDQGcFmaJgB", raising=False)
        monkeypatch.setattr(settings, "elevenlabs_model_id", "eleven_flash_v2_5", raising=False)

        fake_audio = b"\xff\xfb\x90\x00_fake_mp3_bytes"

        with patch("app.api.v1.tts.requests.post", return_value=_fake_response(200, fake_audio)):
            resp = client.post("/api/v1/tts", json={"text": "Knight to f3."})

        assert resp.status_code == 200
        assert resp.content == fake_audio
        assert resp.headers["content-type"] == "audio/mpeg"

    def test_forwards_api_key_and_payload(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "my-secret-key", raising=False)
        monkeypatch.setattr(settings, "elevenlabs_voice_id", "voiceXYZ", raising=False)
        monkeypatch.setattr(settings, "elevenlabs_model_id", "eleven_flash_v2_5", raising=False)

        with patch(
            "app.api.v1.tts.requests.post",
            return_value=_fake_response(200, b"audio"),
        ) as mock_post:
            client.post("/api/v1/tts", json={"text": "Pawn to e4."})

        assert mock_post.call_count == 1
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["xi-api-key"] == "my-secret-key"
        assert "voiceXYZ" in mock_post.call_args[0][0]
        assert call_kwargs["json"]["text"] == "Pawn to e4."
        assert call_kwargs["json"]["model_id"] == "eleven_flash_v2_5"


class TestTTSErrorMapping:
    """Upstream errors map to appropriate HTTP status codes."""

    def test_upstream_401_maps_to_502(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "bad-key", raising=False)
        with patch(
            "app.api.v1.tts.requests.post",
            return_value=_fake_response(401, text="invalid key"),
        ):
            resp = client.post("/api/v1/tts", json={"text": "Knight to f3."})
        assert resp.status_code == 502

    def test_upstream_429_maps_to_429(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "fake-key", raising=False)
        with patch(
            "app.api.v1.tts.requests.post",
            return_value=_fake_response(429, text="quota exceeded"),
        ):
            resp = client.post("/api/v1/tts", json={"text": "Knight to f3."})
        assert resp.status_code == 429

    def test_network_error_maps_to_502(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests

        monkeypatch.setattr(settings, "elevenlabs_api_key", "fake-key", raising=False)
        with patch(
            "app.api.v1.tts.requests.post",
            side_effect=requests.RequestException("connection refused"),
        ):
            resp = client.post("/api/v1/tts", json={"text": "Knight to f3."})
        assert resp.status_code == 502


class TestTTSRateLimit:
    """The in-process per-client rate limiter fires after N requests."""

    def test_returns_429_after_limit_exceeded(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "elevenlabs_api_key", "fake-key", raising=False)

        with patch(
            "app.api.v1.tts.requests.post",
            return_value=_fake_response(200, b"audio"),
        ):
            responses = [client.post("/api/v1/tts", json={"text": f"Move {i}."}) for i in range(21)]

        status_codes = [r.status_code for r in responses]
        assert status_codes[-1] == 429
        # All earlier calls should have succeeded
        assert all(code == 200 for code in status_codes[:-1])
