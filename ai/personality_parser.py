# ai/personality_parser.py
"""
Detect and parse personality update commands from user transcripts.

Examples:
  "Be funnier"           → traits.humor += 0.15
  "Be calmer"            → traits.energy -= 0.15, mode → calm
  "Talk shorter"         → traits.verbosity -= 0.15
  "Switch to bedtime"    → active_mode = bedtime
  "Change your name to Orbit" → name = Orbit
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class PersonalityUpdate:
    """Describes a set of changes to apply to a BotProfile."""
    trait_deltas: dict[str, float] = field(default_factory=dict)
    set_mode: str | None = None
    set_name: str | None = None
    is_command: bool = False


# ── Pattern definitions ──

_TRAIT_UP_PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:be|more)\s+funn(?:ier|y)\b", "humor"),
    (r"\b(?:be|more)\s+warm(?:er)?\b", "warmth"),
    (r"\b(?:be|more)\s+curious\b", "curiosity"),
    (r"\b(?:be|more)\s+energetic\b", "energy"),
    (r"\b(?:talk|be)\s+(?:more\s+)?verbose\b", "verbosity"),
    (r"\b(?:talk|be)\s+(?:more\s+)?(?:long|longer|detailed)\b", "verbosity"),
]

_TRAIT_DOWN_PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:be|more)\s+calm(?:er)?\b", "energy"),
    (r"\b(?:be)\s+(?:less\s+)?(?:serious|quiet)\b", "humor"),
    (r"\b(?:talk|be)\s+(?:more\s+)?(?:short|shorter|brief|concise)\b", "verbosity"),
    (r"\b(?:be)\s+(?:less\s+)?(?:chatty|talkative)\b", "verbosity"),
]

_MODE_PATTERNS: list[tuple[str, str]] = [
    (r"\bswitch\s+to\s+bedtime\b", "bedtime"),
    (r"\bbedtime\s+mode\b", "bedtime"),
    (r"\bswitch\s+to\s+homework\b", "homework"),
    (r"\bhomework\s+mode\b", "homework"),
    (r"\bswitch\s+to\s+creative\b", "creative"),
    (r"\bcreative\s+mode\b", "creative"),
    (r"\bswitch\s+to\s+calm\b", "calm"),
    (r"\bcalm\s+mode\b", "calm"),
    (r"\bnormal\s+mode\b", "default"),
    (r"\bswitch\s+to\s+(?:normal|default)\b", "default"),
]

_NAME_PATTERN = re.compile(
    r"(?:change\s+your\s+name\s+to|call\s+you|your\s+name\s+is)\s+(\w+)",
    re.IGNORECASE,
)

DELTA = 0.15


def parse_personality_command(transcript: str) -> PersonalityUpdate:
    """Parse a transcript for personality configuration commands."""
    text = transcript.lower().strip()
    update = PersonalityUpdate()

    # Trait increases
    for pattern, trait in _TRAIT_UP_PATTERNS:
        if re.search(pattern, text):
            update.trait_deltas[trait] = update.trait_deltas.get(trait, 0) + DELTA
            update.is_command = True

    # Trait decreases
    for pattern, trait in _TRAIT_DOWN_PATTERNS:
        if re.search(pattern, text):
            update.trait_deltas[trait] = update.trait_deltas.get(trait, 0) - DELTA
            update.is_command = True

    # Mode switches
    for pattern, mode in _MODE_PATTERNS:
        if re.search(pattern, text):
            update.set_mode = mode
            update.is_command = True
            break

    # Name changes
    match = _NAME_PATTERN.search(transcript)  # preserve original case
    if match:
        update.set_name = match.group(1).capitalize()
        update.is_command = True

    return update


def apply_trait_deltas(traits: dict, deltas: dict[str, float]) -> dict:
    """Apply trait deltas, clamping to [0, 1]."""
    updated = dict(traits)
    for key, delta in deltas.items():
        current = updated.get(key, 0.5)
        updated[key] = max(0.0, min(1.0, current + delta))
    return updated
