# tests/test_personality_parser.py
"""Tests for the personality command parser."""
from __future__ import annotations

from ai.personality_parser import apply_trait_deltas, parse_personality_command


def test_be_funnier():
    result = parse_personality_command("Be funnier")
    assert result.is_command
    assert "humor" in result.trait_deltas
    assert result.trait_deltas["humor"] > 0


def test_be_calmer():
    result = parse_personality_command("Be calmer please")
    assert result.is_command
    assert "energy" in result.trait_deltas
    assert result.trait_deltas["energy"] < 0


def test_talk_shorter():
    result = parse_personality_command("Talk shorter")
    assert result.is_command
    assert "verbosity" in result.trait_deltas
    assert result.trait_deltas["verbosity"] < 0


def test_switch_to_bedtime():
    result = parse_personality_command("Switch to bedtime mode")
    assert result.is_command
    assert result.set_mode == "bedtime"


def test_change_name():
    result = parse_personality_command("Change your name to Orbit")
    assert result.is_command
    assert result.set_name == "Orbit"


def test_not_a_command():
    result = parse_personality_command("Tell me about dinosaurs")
    assert not result.is_command
    assert result.trait_deltas == {}
    assert result.set_mode is None
    assert result.set_name is None


def test_apply_trait_deltas_clamps():
    traits = {"humor": 0.95}
    updated = apply_trait_deltas(traits, {"humor": 0.15})
    assert updated["humor"] == 1.0  # clamped

    traits = {"energy": 0.05}
    updated = apply_trait_deltas(traits, {"energy": -0.15})
    assert updated["energy"] == 0.0  # clamped


def test_multiple_commands():
    result = parse_personality_command("Be funnier and switch to creative mode")
    assert result.is_command
    assert "humor" in result.trait_deltas
    assert result.set_mode == "creative"
