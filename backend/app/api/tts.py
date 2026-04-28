"""Text-to-speech proxy.

Authenticated, server-side proxy to one of several TTS providers. Decouples
the frontend from upstream keys and URLs — the browser only ever talks to
``/api/v1/tts/...`` on its own origin, and credentials never cross the wire.

Supported backends (each enabled when its key is configured):

  * ``qwen``       — Alibaba DashScope hosting Qwen3-TTS.
  * ``elevenlabs`` — ElevenLabs hosted TTS, paid per character.

For the v1 cut both expose a single ``/sentence`` endpoint that returns a
full audio body per request. Sentence-level chunking is what the EPUB
reader's ``TtsController`` already uses, and a one-shot blob per sentence
is much simpler than wiring streamed chunks through the browser.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.config import get_settings
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])

Backend = Literal["qwen", "elevenlabs"]


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
    }


@router.post("/sentence")
async def synthesize_sentence(
    body: TtsRequest,
    _user: User = Depends(get_current_user),
) -> Response:
    """Synthesize one sentence and return its audio body.

    Caller is expected to chunk long passages into sentence-sized pieces
    upstream — the Web Speech path already does this, so the cloud
    backends match the same contract. The response media-type depends
    on the backend (Qwen returns WAV, ElevenLabs returns MP3).
    """
    if body.backend == "qwen":
        return await _synth_qwen(body)
    if body.backend == "elevenlabs":
        return await _synth_elevenlabs(body)
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
            audio_resp = await client.get(audio_url)
        audio_resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("DashScope audio download failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS audio download failed",
        ) from exc

    return Response(
        content=audio_resp.content,
        media_type=audio_resp.headers.get("content-type", "audio/wav"),
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
            r = await client.post(
                url,
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        logger.warning("ElevenLabs TTS call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TTS upstream unreachable",
        ) from exc

    if r.status_code != 200:
        logger.warning(
            "ElevenLabs returned %s: %s", r.status_code, r.text[:300]
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS upstream error ({r.status_code})",
        )

    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "audio/mpeg"),
    )
