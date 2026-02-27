# services/openai_stt.py
from __future__ import annotations

import logging
from pathlib import Path

from openai import AsyncOpenAI
from api.app.config import get_settings

logger = logging.getLogger(__name__)


class NonRetryableJobError(Exception):
    """Raised when input is permanently invalid and should not be retried."""
    pass


def _validate_audio_file(path: Path) -> None:
    if not path.exists():
        raise NonRetryableJobError(f"Audio file does not exist: {path}")

    size = path.stat().st_size
    if size < 1024:  # way too small to be real audio
        head = path.read_bytes()
        text_preview = head.decode("utf-8", errors="replace")

        raise NonRetryableJobError(
            f"Audio file too small ({size} bytes). "
            f"Likely not real audio. Preview:\n{text_preview}"
        )

    head = path.read_bytes()[:16]

    # Validate WAV container if extension says .wav
    if path.suffix.lower() == ".wav":
        if not (head.startswith(b"RIFF") and b"WAVE" in head[:16]):
            raise NonRetryableJobError(
                f"Invalid WAV container. Header={head!r}"
            )


async def transcribe_audio(audio_path: str | Path) -> str:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    path = Path(audio_path)

    logger.info("STT: transcribing %s", path)

    # ✅ Validate before sending to OpenAI
    _validate_audio_file(path)

    with path.open("rb") as f:
        response = await client.audio.transcriptions.create(
            model=settings.openai_stt_model,
            file=f,
            response_format="text",
        )

    transcript = response.strip()
    logger.info("STT: got %d chars", len(transcript))
    return transcript