"""Server-side ElevenLabs TTS proxy (REVIEW-009 upgrade).

Keeps the API key out of the browser bundle. When the key is empty (the
dev/CI default) every request returns 503 and the frontend silently falls
back to the browser's built-in speechSynthesis engine.

Free-tier budget guardrails:
- Max 500 characters per request (roughly 30 seconds of speech).
- 20 requests per user per minute (in-process rate limit).
"""

import logging
import time
from collections import defaultdict
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.database import settings

router = APIRouter(prefix="/tts", tags=["tts"])
logger = logging.getLogger(__name__)

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MAX_CHARS = 500
RATE_LIMIT_PER_MINUTE = 20

_tts_buckets: defaultdict[str, list[float]] = defaultdict(list)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_CHARS)


def reset_tts_rate_limits() -> None:
    """Clear in-process TTS rate-limit state (for tests)."""
    _tts_buckets.clear()


def _rate_limit(client_id: str) -> None:
    """Allow N TTS requests per minute per client IP."""
    now = time.monotonic()
    window_start = now - 60.0
    hits = [t for t in _tts_buckets[client_id] if t > window_start]
    _tts_buckets[client_id] = hits
    if len(hits) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many TTS requests. Try again in a minute.",
        )
    hits.append(now)


@router.post("")
def synthesize(body: TTSRequest, request: Request) -> Response:
    """Convert text to speech via ElevenLabs and return MP3 audio.

    Returns 503 when no API key is configured; the frontend treats that
    as a signal to fall back to the browser's speechSynthesis engine.
    """
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS not configured; using browser speech fallback.",
        )

    client_id = request.client.host if request.client else "unknown"
    _rate_limit(client_id)

    url = ELEVENLABS_TTS_URL.format(voice_id=settings.elevenlabs_voice_id)
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload: dict[str, Any] = {
        "text": body.text,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "speed": 0.92,
        },
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
    except requests.RequestException as exc:
        logger.error("ElevenLabs request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS provider unreachable.",
        ) from exc

    if resp.status_code == 401:
        logger.error("ElevenLabs auth rejected — check ELEVENLABS_API_KEY value.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS provider rejected credentials.",
        )

    if resp.status_code == 422:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"TTS rejected text: {resp.text[:200]}",
        )

    if resp.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ElevenLabs monthly quota exceeded — falling back.",
        )

    if resp.status_code != 200:
        logger.warning("ElevenLabs error %d: %s", resp.status_code, resp.text[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS generation failed.",
        )

    return Response(content=resp.content, media_type="audio/mpeg")
