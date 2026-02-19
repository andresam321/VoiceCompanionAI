# services/openai_stt.py
from __future__ import annotations

import logging
from pathlib import Path

from openai import AsyncOpenAI

from api.app.config import get_settings

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_path: str | Path) -> str:
    """Transcribe an audio file using OpenAI Whisper."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    path = Path(audio_path)

    logger.info("STT: transcribing %s", path.name)
    with path.open("rb") as f:
        response = await client.audio.transcriptions.create(
            model=settings.openai_stt_model,
            file=f,
            response_format="text",
        )
    transcript = response.strip()
    logger.info("STT: got %d chars", len(transcript))
    return transcript
