# tests/test_emotion_detector.py
"""Tests for the emotion detection pipeline."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.emotion_detector import (
    EMOTION_LABELS,
    EmotionResult,
    detect_emotion,
    detect_emotion_from_audio,
    detect_emotion_from_transcript,
)


@pytest.mark.asyncio
async def test_audio_emotion_returns_valid_label():
    result = await detect_emotion_from_audio("/tmp/fake.wav")
    assert result is not None
    assert result.label in EMOTION_LABELS
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_transcript_emotion_fallback():
    mock_json = '{"emotion": "happy", "confidence": 0.85}'
    with patch("services.emotion_detector.extract_json", new_callable=AsyncMock, return_value=mock_json):
        result = await detect_emotion_from_transcript("I'm having a great day!")
    assert result.label == "happy"
    assert result.confidence == 0.85


@pytest.mark.asyncio
async def test_full_pipeline_uses_audio_when_confident():
    audio_result = EmotionResult(label="excited", confidence=0.9)
    with patch("services.emotion_detector.detect_emotion_from_audio", new_callable=AsyncMock, return_value=audio_result):
        result = await detect_emotion("/tmp/fake.wav", "yay!")
    assert result.label == "excited"


@pytest.mark.asyncio
async def test_full_pipeline_falls_back_to_transcript():
    audio_result = EmotionResult(label="neutral", confidence=0.3)  # low confidence
    transcript_result = EmotionResult(label="sad", confidence=0.7)
    with (
        patch("services.emotion_detector.detect_emotion_from_audio", new_callable=AsyncMock, return_value=audio_result),
        patch("services.emotion_detector.detect_emotion_from_transcript", new_callable=AsyncMock, return_value=transcript_result),
    ):
        result = await detect_emotion("/tmp/fake.wav", "I'm feeling down today")
    assert result.label == "sad"
