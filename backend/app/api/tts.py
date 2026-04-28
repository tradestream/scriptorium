"""Text-to-speech proxy.

Authenticated, server-side proxy to Alibaba's DashScope multimodal-generation
endpoint serving Qwen3-TTS. Decouples the frontend from the upstream key and
URL — the browser only ever talks to ``/api/v1/tts/...`` on its own origin.

For the v1 cut we expose a single ``/sentence`` endpoint that returns a full
WAV body per request. Sentence-level chunking is what the EPUB reader's
``TtsController`` already uses, and a one-shot WAV per sentence is much
simpler than wiring base64-PCM SSE chunks through to the browser. Streaming
mode can be added later when latency becomes an issue.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.config import get_settings
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: Optional[str] = None
    language_type: Optional[str] = None
    model: Optional[str] = None


@router.get("/config")
async def get_tts_config(_user: User = Depends(get_current_user)):
    """Tell the frontend whether the cloud TTS backend is wired up.

    The browser uses this to decide whether to expose the "Cloud" toggle.
    """
    settings = get_settings()
    return {
        "cloud_available": bool(settings.DASHSCOPE_API_KEY),
        "default_voice": settings.QWEN_TTS_VOICE,
        "default_model": settings.QWEN_TTS_MODEL,
    }


@router.post("/sentence")
async def synthesize_sentence(
    body: TtsRequest,
    _user: User = Depends(get_current_user),
) -> Response:
    """Synthesize one sentence to a WAV body.

    Caller is expected to chunk long passages into sentence-sized pieces
    upstream — Qwen3-TTS-flash is tuned for short utterances, and our
    Web Speech path already does this chunking, so the cloud backend
    matches the same contract.
    """
    settings = get_settings()
    if not settings.DASHSCOPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloud TTS is not configured (DASHSCOPE_API_KEY missing)",
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
        logger.warning(
            "DashScope returned %s: %s", r.status_code, r.text[:300]
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS upstream error ({r.status_code})",
        )

    # Non-streaming responses come back as JSON with an audio URL inside
    # ``output.audio.url``. Fetch the audio bytes here so the frontend
    # gets a clean ``audio/wav`` body and never sees the upstream URL.
    data = r.json()
    audio = (data.get("output") or {}).get("audio") or {}
    audio_url = audio.get("url")
    if not audio_url:
        # Some flows return inline base64 instead; surface that too.
        b64 = audio.get("data")
        if b64:
            import base64
            return Response(
                content=base64.b64decode(b64),
                media_type="audio/wav",
            )
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
