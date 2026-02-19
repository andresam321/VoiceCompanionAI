# services/openai_tts.py
from __future__ import annotations

import logging
from pathlib import Path

from openai import AsyncOpenAI

from api.app.config import get_settings

logger = logging.getLogger(__name__)


async def synthesize_speech(text: str, output_path: str | Path, voice: str | None = None) -> Path:
    """Generate speech audio from text and save to output_path."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    voice = voice or settings.openai_tts_voice
    logger.info("TTS: synthesizing %d chars with voice=%s", len(text), voice)

    response = await client.audio.speech.create(
        model=settings.openai_tts_model,
        voice=voice,
        input=text,
        response_format="wav",
    )
    response.stream_to_file(str(out))
    logger.info("TTS: saved to %s", out)
    return out
