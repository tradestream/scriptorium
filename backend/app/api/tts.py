"""Text-to-speech proxy.

Authenticated, server-side proxy to one of several TTS providers. Decouples
the frontend from upstream keys and URLs — the browser only ever talks to
``/api/v1/tts/...`` on its own origin, and credentials never cross the wire.

Supported backends (each enabled when its key/URL is configured):

  * ``qwen``       — Alibaba DashScope hosting Qwen3-TTS.
  * ``elevenlabs`` — ElevenLabs hosted TTS, paid per character.
  * ``local``      — OpenAI-compatible server on the LAN (typically
                     ``mlx_audio.server`` running Qwen3-TTS on an
                     Apple Silicon Mac).

For the v1 cut both expose a single ``/sentence`` endpoint that returns a
full audio body per request. Sentence-level chunking is what the EPUB
reader's ``TtsController`` already uses, and a one-shot blob per sentence
is much simpler than wiring streamed chunks through the browser.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.auth import get_current_user
from app.config import get_settings
from app.models import User
from app.services.auth import verify_token
from app.utils.url_safety import BodyTooLargeError, fetch_capped

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])

Backend = Literal["qwen", "elevenlabs", "local"]

# Per-sentence audio body cap. A 4000-character sentence at 16-bit / 24 kHz
# WAV runs ~7-9 MB; a noisy or buggy upstream returning much more should
# be refused before we relay it to the browser.
MAX_AUDIO_BODY_BYTES = 20 * 1024 * 1024


def _validate_audio_response(
    headers: dict, body: bytes, source: str
) -> None:
    """Reject a TTS upstream that returned anything that doesn't smell
    like an audio body. Strict on content-type because relaying
    text/html (an upstream error page) to a browser ``<audio>`` element
    leaks information without playing anything useful.
    """
    ct = (headers.get("content-type") or "").lower()
    if not (ct.startswith("audio/") or ct == "application/octet-stream"):
        logger.warning(
            "%s returned non-audio content-type %r; refusing to relay",
            source,
            ct,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS upstream returned non-audio content ({ct})",
        )
    if not body:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{source} returned empty body",
        )


def _tts_rate_key(request: Request) -> str:
    """Rate-limit key keyed by user id when the bearer token is present,
    falling back to remote address. Per-user is the right shape because
    cloud TTS is billed per character and a single user can spend many
    sentences in quick succession; IP-only would let a shared-NAT
    household trade the budget but also let one household crowd out the
    rest. The token verify is cheap (HMAC, no DB).
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        payload = verify_token(token)
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return get_remote_address(request)


# Dedicated limiter for the TTS proxy. Separate from the global limiter
# so we can use a per-user key without rewiring the rest of the API. The
# global SlowAPIMiddleware catches the RateLimitExceeded exception this
# limiter raises, so no extra wiring is needed.
_tts_limiter = Limiter(key_func=_tts_rate_key, default_limits=[])


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    backend: Backend = "qwen"
    voice: Optional[str] = None
    language_type: Optional[str] = None
    model: Optional[str] = None


@router.get("/config")
async def get_tts_config(_user: User = Depends(get_current_user)):
    """Tell the frontend which cloud TTS backends are wired up.

    The browser uses this to decide which buttons to expose in the
    backend toggle. Returns a per-backend block with availability and
    that backend's defaults so the UI doesn't have to mirror them.
    """
    s = get_settings()
    return {
        "qwen": {
            "available": bool(s.DASHSCOPE_API_KEY),
            "default_voice": s.QWEN_TTS_VOICE,
            "default_model": s.QWEN_TTS_MODEL,
        },
        "elevenlabs": {
            "available": bool(s.ELEVENLABS_API_KEY),
            "default_voice": s.ELEVENLABS_VOICE,
            "default_model": s.ELEVENLABS_MODEL,
        },
        "local": {
            "available": bool(s.LOCAL_TTS_URL),
            "default_voice": s.LOCAL_TTS_VOICE,
            "default_model": s.LOCAL_TTS_MODEL,
        },
    }


@router.post("/sentence")
@_tts_limiter.limit("30/minute")
async def synthesize_sentence(
    request: Request,
    body: TtsRequest,
    _user: User = Depends(get_current_user),
) -> Response:
    """Synthesize one sentence and return its audio body.

    Caller is expected to chunk long passages into sentence-sized pieces
    upstream — the Web Speech path already does this, so the cloud
    backends match the same contract. The response media-type depends
    on the backend (Qwen returns WAV, ElevenLabs returns MP3).

    Rate-limited tightly (30/min per user) because cloud backends are
    billed per-character. 30 sentences/min is faster than anyone reads
    aloud, but tight enough that automation can't drain a paid quota
    in seconds.
    """
    if body.backend == "qwen":
        return await _synth_qwen(body)
    if body.backend == "elevenlabs":
        return await _synth_elevenlabs(body)
    if body.backend == "local":
        return await _synth_local(body)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown TTS backend: {body.backend!r}",
    )


# ── Qwen3-TTS via DashScope ──────────────────────────────────────────

async def _synth_qwen(body: TtsRequest) -> Response:
    settings = get_settings()
    if not settings.DASHSCOPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qwen TTS is not configured (DASHSCOPE_API_KEY missing)",
        )

    payload = {
        "model": body.model or settings.QWEN_TTS_MODEL,
        "input": {
            "text": body.text,
            "voice": body.voice or settings.QWEN_TTS_VOICE,
        },
    }
    if body.language_type:
        payload["input"]["language_type"] = body.language_type

    url = (
        f"{settings.DASHSCOPE_BASE_URL.rstrip('/')}"
        "/api/v1/services/aigc/multimodal-generation/generation"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        logger.warning("DashScope TTS call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS upstream unreachable",
        ) from exc

    if r.status_code != 200:
        logger.warning("DashScope returned %s: %s", r.status_code, r.text[:300])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS upstream error ({r.status_code})",
        )

    data = r.json()
    audio = (data.get("output") or {}).get("audio") or {}
    audio_url = audio.get("url")
    if not audio_url:
        b64 = audio.get("data")
        if b64:
            import base64
            return Response(content=base64.b64decode(b64), media_type="audio/wav")
        logger.warning("DashScope response missing audio: %s", data)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS upstream returned no audio",
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            status_code, headers, audio_body = await fetch_capped(
                client, audio_url, max_bytes=MAX_AUDIO_BODY_BYTES
            )
    except BodyTooLargeError as exc:
        logger.warning("DashScope audio body exceeded cap: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS upstream returned an oversized audio body",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("DashScope audio download failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS audio download failed",
        ) from exc
    if status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS audio download error ({status_code})",
        )
    _validate_audio_response(headers, audio_body, "DashScope")
    return Response(
        content=audio_body,
        media_type=headers.get("content-type", "audio/wav"),
    )


# ── ElevenLabs ───────────────────────────────────────────────────────

async def _synth_elevenlabs(body: TtsRequest) -> Response:
    settings = get_settings()
    if not settings.ELEVENLABS_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ElevenLabs TTS is not configured (ELEVENLABS_API_KEY missing)",
        )

    voice_id = body.voice or settings.ELEVENLABS_VOICE
    payload = {
        "text": body.text,
        "model_id": body.model or settings.ELEVENLABS_MODEL,
    }

    url = (
        f"{settings.ELEVENLABS_BASE_URL.rstrip('/')}"
        f"/v1/text-to-speech/{voice_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            status_code, headers, body = await fetch_capped(
                client,
                url,
                method="POST",
                max_bytes=MAX_AUDIO_BODY_BYTES,
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json=payload,
            )
    except BodyTooLargeError as exc:
        logger.warning("ElevenLabs body exceeded cap: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS upstream returned an oversized audio body",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("ElevenLabs TTS call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS upstream unreachable",
        ) from exc

    if status_code != 200:
        logger.warning("ElevenLabs returned %s", status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS upstream error ({status_code})",
        )
    _validate_audio_response(headers, body, "ElevenLabs")
    return Response(
        content=body,
        media_type=headers.get("content-type", "audio/mpeg"),
    )


# ── Local Apple-Silicon Qwen3-TTS via mlx-audio ──────────────────────

async def _synth_local(body: TtsRequest) -> Response:
    """Try each configured local server in order; first success wins.

    Connect timeout is short (2 s) so a sleeping laptop falls through to
    the always-on Mac quickly. Read timeout stays generous because the
    cold-start model load can take 10-30 s.
    """
    settings = get_settings()
    urls = [
        u.strip().rstrip("/")
        for u in (settings.LOCAL_TTS_URL or "").split(",")
        if u.strip()
    ]
    if not urls:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local TTS is not configured (LOCAL_TTS_URL missing)",
        )

    payload = {
        "model": body.model or settings.LOCAL_TTS_MODEL,
        "input": body.text,
        "voice": body.voice or settings.LOCAL_TTS_VOICE,
    }
    timeout = httpx.Timeout(connect=2.0, read=120.0, write=10.0, pool=10.0)

    last_detail = "no candidates tried"
    for url in urls:
        full_url = f"{url}/v1/audio/speech"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                status_code, headers, body = await fetch_capped(
                    client,
                    full_url,
                    method="POST",
                    max_bytes=MAX_AUDIO_BODY_BYTES,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
        except BodyTooLargeError as exc:
            logger.warning("Local TTS at %s exceeded body cap: %s", url, exc)
            last_detail = f"{url} oversized body"
            continue
        except httpx.HTTPError as exc:
            logger.info("Local TTS at %s unreachable, falling through: %s", url, exc)
            last_detail = f"{url} unreachable: {exc.__class__.__name__}"
            continue

        if status_code == 200:
            _validate_audio_response(headers, body, f"Local TTS ({url})")
            return Response(
                content=body,
                media_type=headers.get("content-type", "audio/wav"),
            )
        logger.info("Local TTS at %s returned %s, trying next", url, status_code)
        last_detail = f"{url} → {status_code}"

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"All local TTS servers failed: {last_detail}",
    )
