# tests/test_prompt_builder.py
"""Tests for the prompt builder — verifies layered prompt assembly."""
from __future__ import annotations

from ai.prompt_builder import PromptContext, build_system_prompt


def test_build_includes_bot_name():
    ctx = PromptContext(bot_name="Orbit")
    prompt = build_system_prompt(ctx)
    assert "Orbit" in prompt


def test_build_includes_traits():
    ctx = PromptContext(warmth=0.95, humor=0.3)
    prompt = build_system_prompt(ctx)
    assert "0.95" in prompt
    assert "0.3" in prompt


def test_build_includes_safety_layer():
    ctx = PromptContext(safety_enabled=True)
    prompt = build_system_prompt(ctx)
    assert "SAFETY RULES" in prompt


def test_build_excludes_safety_when_disabled():
    ctx = PromptContext(safety_enabled=False)
    prompt = build_system_prompt(ctx)
    assert "SAFETY RULES" not in prompt


def test_build_includes_mode_overlay():
    ctx = PromptContext(active_mode="bedtime")
    prompt = build_system_prompt(ctx)
    assert "Bedtime" in prompt


def test_build_includes_memories():
    ctx = PromptContext(memories=["Loves dinosaurs", "Favorite color is blue"])
    prompt = build_system_prompt(ctx)
    assert "Loves dinosaurs" in prompt
    assert "Favorite color is blue" in prompt


def test_build_includes_user_profile():
    ctx = PromptContext(user_profile_summary="A creative kid who loves space.")
    prompt = build_system_prompt(ctx)
    assert "creative kid" in prompt


def test_build_includes_emotion_context():
    ctx = PromptContext(detected_emotion="sad", emotion_confidence=0.8)
    prompt = build_system_prompt(ctx)
    assert "sad" in prompt
    assert "80%" in prompt


def test_build_excludes_neutral_emotion():
    ctx = PromptContext(detected_emotion="neutral", emotion_confidence=0.9)
    prompt = build_system_prompt(ctx)
    assert "EMOTIONAL CONTEXT" not in prompt


def test_bot_profile_injection():
    """Core test: bot profile fields appear in assembled prompt."""
    ctx = PromptContext(
        bot_name="Sparky",
        warmth=0.8,
        humor=0.9,
        active_mode="creative",
        memories=["Likes building robots"],
        detected_emotion="excited",
        emotion_confidence=0.75,
    )
    prompt = build_system_prompt(ctx)
    assert "Sparky" in prompt
    assert "0.9" in prompt
    assert "Creative" in prompt
    assert "Likes building robots" in prompt
    assert "excited" in prompt
