"""Voice endpoints: ElevenLabs TTS proxy, the free-voice catalog, and prefs.

REVIEW-009 narration + Phase 12 AI-coach voice. Keeps the API key out of the
browser bundle. When the key is empty (the dev/CI default) or the key lacks the
text_to_speech permission the provider rejects us, every request returns an
error and the frontend silently falls back to the browser's speechSynthesis.

Free-voice catalog: a small, curated allowlist of free-tier ElevenLabs premade
voices. A client may only ever select a voice from this list — the id is
validated against it both on the TTS request and when persisting a preference —
so an arbitrary string can never be interpolated into the provider URL.

Free-tier budget guardrails:
- Max 500 characters per request (roughly 30 seconds of speech).
- 20 requests per user per minute (in-process rate limit).
"""

import logging
import time
from collections import defaultdict
from typing import Annotated, Any

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import enforce_same_origin, get_current_user, get_db_session
from app.api.v1.schemas import (
    ErrorResponse,
    VoiceListResponse,
    VoiceOption,
    VoicePreferencesResponse,
    VoicePreferencesUpdate,
)
from app.core.database import settings
from app.models.user import User

router = APIRouter(tags=["voice"])
logger = logging.getLogger(__name__)

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MAX_CHARS = 500
RATE_LIMIT_PER_MINUTE = 20

# Curated free-tier premade voices. `name` is for the picker; the `id` is the
# only value ever accepted from a client and the only one interpolated into the
# provider URL. These require the API key to carry the text_to_speech scope.
# Free-tier premade voices, narrowed to the ids the free-plan API actually
# synthesizes: Adam and George both return audio on a free key, whereas the
# shared "library" voice Rachel returns 402 paid_plan_required and the former
# Daniel id 404s. Keeping this list to verified-working ids means every picker
# option speaks instead of silently falling back to the robotic browser voice.
FREE_ELEVEN_VOICES: tuple[tuple[str, str], ...] = (
    ("pNInz6obpgDQGcFmaJgB", "Adam"),
    ("JBFqnCBsd6RMkjVDRZzb", "George"),
)
_ALLOWED_VOICE_IDS = frozenset(voice_id for voice_id, _ in FREE_ELEVEN_VOICES)

_tts_buckets: defaultdict[str, list[float]] = defaultdict(list)

_CurrentUser = Depends(get_current_user)  # noqa: E402
_DbSession = Depends(get_db_session)  # noqa: E402
_SameOrigin = Depends(enforce_same_origin)  # noqa: E402


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_CHARS)
    # Optional selectable voice; must be one of the allowlisted ids. Empty or
    # absent falls back to the configured default voice.
    voice: str = Field(default="", max_length=64)


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


def _resolve_voice(requested: str) -> str:
    """Map a client-supplied voice to an allowed id, defaulting when empty.

    Anything not in the allowlist is rejected: the returned id is interpolated
    into the provider URL, so this is the trust boundary.
    """
    if not requested:
        return settings.elevenlabs_voice_id
    if requested not in _ALLOWED_VOICE_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown voice. Choose one from the available list.",
        )
    return requested


@router.get("/tts/voices", response_model=VoiceListResponse)
def list_voices() -> VoiceListResponse:
    """The curated free-tier ElevenLabs voices (browser voices are enumerated
    client-side). `available` is False when no key is configured, so the picker
    can present them honestly instead of offering a voice that only 502s."""
    configured = bool(settings.elevenlabs_api_key)
    return VoiceListResponse(
        voices=[
            VoiceOption(id=voice_id, name=name, engine="eleven", available=configured)
            for voice_id, name in FREE_ELEVEN_VOICES
        ]
    )


@router.post("/tts")
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

    voice_id = _resolve_voice(body.voice)

    client_id = request.client.host if request.client else "unknown"
    _rate_limit(client_id)

    url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)
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
        # ElevenLabs distinguishes a bad key from a key that authenticates but
        # lacks the `text_to_speech` scope. The provider's detail carries the
        # reason and never echoes the key, so log it to make an
        # "works-elsewhere-but-not-here" key-permission issue self-evident.
        logger.error("ElevenLabs rejected the request (401): %s", resp.text[:300])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "TTS provider rejected the request — verify ELEVENLABS_API_KEY "
                "is valid and granted the text_to_speech permission."
            ),
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


def _prefs(user: User) -> VoicePreferencesResponse:
    return VoicePreferencesResponse(voice_authorized=user.voice_authorized, voice_id=user.voice_id)


@router.get(
    "/me/voice",
    response_model=VoicePreferencesResponse,
    responses={401: {"model": ErrorResponse}},
)
def get_voice_preferences(
    current_user: Annotated[User, _CurrentUser],
) -> VoicePreferencesResponse:
    """The caller's stored voice consent + selected voice."""
    return _prefs(current_user)


@router.put(
    "/me/voice",
    response_model=VoicePreferencesResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    dependencies=[_SameOrigin],
)
def update_voice_preferences(
    payload: VoicePreferencesUpdate,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> VoicePreferencesResponse:
    """Persist the caller's voice consent and/or selected voice.

    `voice_id` is a short preference string the client chooses how to interpret:
    empty means the browser default, an allowlisted id is an ElevenLabs voice,
    any other value is the name of an OS voice. Storing it is harmless — the
    only place a voice id reaches the provider is `POST /tts`, which re-validates
    against the allowlist, so a browser name can never be interpolated into the
    ElevenLabs URL.
    """
    if payload.voice_id is not None:
        current_user.voice_id = payload.voice_id.strip()
    if payload.voice_authorized is not None:
        current_user.voice_authorized = payload.voice_authorized
    db.commit()
    db.refresh(current_user)
    return _prefs(current_user)
