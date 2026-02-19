# services/emotion_detector.py
"""
Emotion detection pipeline.

1. Primary: analyze audio tone features (stub — replace with a real model
   like wav2vec2-emotion or a fine-tuned classifier).
2. Fallback: sentiment analysis on the transcript via LLM.
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass

from services.openai_llm import extract_json

logger = logging.getLogger(__name__)

EMOTION_LABELS = ["neutral", "happy", "sad", "angry", "anxious", "excited", "tired"]


@dataclass
class EmotionResult:
    label: str
    confidence: float


async def detect_emotion_from_audio(audio_path: str) -> EmotionResult | None:
    """
    Stub: Analyze audio features for emotional tone.

    In production, replace with an actual audio emotion model
    (e.g., HuggingFace wav2vec2-large-xlsr-53-emotion).
    """
    # ── STUB: random realistic output for development ──
    try:
        label = random.choice(EMOTION_LABELS)
        confidence = round(random.uniform(0.45, 0.95), 2)
        logger.info("AudioEmotion(stub): %s @ %.2f", label, confidence)
        return EmotionResult(label=label, confidence=confidence)
    except Exception as exc:
        logger.warning("Audio emotion detection failed: %s", exc)
        return None


async def detect_emotion_from_transcript(transcript: str) -> EmotionResult:
    """Fallback: use LLM to classify emotional tone from text."""
    system = (
        "You are an emotion classifier. Given the user's transcript, respond with "
        'JSON: {"emotion": "<label>", "confidence": <float 0-1>}. '
        f"Labels: {', '.join(EMOTION_LABELS)}."
    )
    try:
        raw = await extract_json(system, transcript)
        data = json.loads(raw)
        return EmotionResult(
            label=data.get("emotion", "neutral"),
            confidence=float(data.get("confidence", 0.5)),
        )
    except Exception as exc:
        logger.warning("Transcript emotion fallback failed: %s", exc)
        return EmotionResult(label="neutral", confidence=0.3)


async def detect_emotion(audio_path: str, transcript: str) -> EmotionResult:
    """Run full emotion detection pipeline: audio first, then transcript fallback."""
    result = await detect_emotion_from_audio(audio_path)
    if result and result.confidence >= 0.5:
        return result
    logger.info("Falling back to transcript-based emotion detection")
    return await detect_emotion_from_transcript(transcript)
