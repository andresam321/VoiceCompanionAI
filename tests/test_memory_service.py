# tests/test_memory_service.py
"""
Tests for memory extraction logic (mocking the LLM calls).
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from services.memory_service import extract_memories


@pytest.mark.asyncio
async def test_extract_memories_returns_list():
    mock_response = json.dumps({
        "memories": [
            {
                "content": "User likes dinosaurs",
                "category": "preference",
                "emotional_context": "happy",
                "salience": 0.8,
            }
        ]
    })
    with patch("services.memory_service.extract_json", new_callable=AsyncMock, return_value=mock_response):
        result = await extract_memories(
            transcript="I really love dinosaurs!",
            assistant_reply="That's awesome! What's your favorite dinosaur?",
            detected_emotion="happy",
        )
    assert len(result) == 1
    assert result[0]["content"] == "User likes dinosaurs"
    assert result[0]["category"] == "preference"


@pytest.mark.asyncio
async def test_extract_memories_empty_when_nothing_notable():
    mock_response = json.dumps({"memories": []})
    with patch("services.memory_service.extract_json", new_callable=AsyncMock, return_value=mock_response):
        result = await extract_memories("hi", "hello!", "neutral")
    assert result == []


@pytest.mark.asyncio
async def test_extract_memories_handles_error():
    with patch("services.memory_service.extract_json", new_callable=AsyncMock, side_effect=Exception("API Error")):
        result = await extract_memories("test", "test", "neutral")
    assert result == []
