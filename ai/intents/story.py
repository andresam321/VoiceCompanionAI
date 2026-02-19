# ai/intents/story.py
from __future__ import annotations

import random
import re

STORY_INTENT = "bedtime_story"

# Kids are fuzzy. Keep triggers broad.
STORY_TRIGGERS = [
    "bedtime",
    "sleep",
    "night",
    "story",
    "tell me a story",
    "read me a story",
]
CHARACTER_KEYWORDS = [
    "bluey",
    "elsa",
    "spiderman",
    "mario",
    "sonic",
    "peppa pig",
]

# Friendly defaults so the bot never stalls
DEFAULT_THEMES = [
    "a cozy forest adventure with a friendly owl",
    "a gentle space trip to visit a sleepy moon",
    "a magical cloud kingdom with soft glowing stars",
    "a calm ocean journey with a kind whale",
    "a quiet cabin on a rainy night with warm cocoa",
]

THEME_KEYWORDS = {
    "space": ["space", "stars", "star", "moon", "planet", "rocket", "galaxy", "astronaut", "comet"],
    "dinosaurs": ["dinosaur", "dinosaurs", "t-rex", "trex", "triceratops", "jurassic", "raptor"],
    "ocean": ["ocean", "sea", "whale", "dolphin", "reef", "fish", "mermaid"],
    "forest": ["forest", "woods", "trees", "owl", "campfire", "cabin"],
    "animals": ["animal", "puppy", "dog", "cat", "bunny", "bear", "fox", "lion", "tiger"],
    "fantasy": ["magic", "wizard", "dragon", "princess", "castle", "fairy", "unicorn"],
    "robots": ["robot", "robots", "machine", "android"],
}


def detect_bedtime_story_request(text: str) -> bool:
    """
    Kid-friendly intent detection.
    If the message contains any story-ish keyword, treat as a story request.
    """
    t = (text or "").lower()
    return any(trigger in t for trigger in STORY_TRIGGERS)


def _extract_length(text: str) -> str | None:
    t = text.lower()
    if any(x in t for x in ["short", "quick", "tiny", "1 minute", "2 minutes", "3 minutes"]):
        return "short"
    if any(x in t for x in ["long", "longer", "big story", "5 minutes", "10 minutes"]):
        return "long"
    return None


def _extract_audience(text: str) -> str | None:
    t = text.lower()
    if any(x in t for x in ["my kid", "my child", "for kids", "for my daughter", "for my son"]):
        return "kid"
    if any(x in t for x in ["for me", "adult", "grown", "for adults"]):
        return "adult"
    return None


def _extract_theme(text: str) -> str | None:
    """
    Extract story theme in kid-friendly way.
    Priority:
    1. Character detection
    2. Multi-bucket mashups
    3. Single bucket
    4. "about X"
    """

    t = (text or "").lower().strip()
    if not t:
        return None

    # ─────────────────────────────────────────────
    # 1️⃣ Character detection FIRST
    # ─────────────────────────────────────────────
    for character in CHARACTER_KEYWORDS:
        if character in t:
            return character

    # ─────────────────────────────────────────────
    # 2️⃣ Keyword buckets
    # ─────────────────────────────────────────────
    matched_buckets = []
    for k, words in THEME_KEYWORDS.items():
        if any(w in t for w in words):
            matched_buckets.append(k)

    # Multi-bucket mashup → keep raw kid phrase
    if len(matched_buckets) >= 2:
        return text.strip()[:64]

    if len(matched_buckets) == 1:
        return matched_buckets[0]

    # ─────────────────────────────────────────────
    # 3️⃣ "about X" fallback
    # ─────────────────────────────────────────────
    m = re.search(r"\babout\s+(.+)$", t)
    if m:
        theme = m.group(1).strip()
        if theme:
            return theme[:64]

    return None


def extract_story_slots(text: str) -> dict:
    """
    Robust slot extraction for kids.
    If theme is unclear, we don't fail—we fallback later.
    """
    raw = (text or "").strip()
    t = raw.lower()

    slots: dict = {}

    length = _extract_length(t)
    if length:
        slots["length"] = length

    audience = _extract_audience(t)
    if audience:
        slots["audience"] = audience

    theme = _extract_theme(t)
    if theme:
        slots["theme"] = theme

    return slots


def normalize_or_fallback_theme(text: str, slots: dict) -> dict:
    """
    If kid input is nonsense or theme wasn't captured, pick something:
    - Use a cleaned snippet of what they said if it's not empty and not just 'story'
    - Otherwise choose a safe default theme
    """
    if slots.get("theme"):
        return slots

    raw = (text or "").strip()
    t = raw.lower()

    # If they said something like "story" / "tell me a story" with no extra content
    generic_only = any(trigger == t for trigger in ["story", "bedtime", "sleep", "night"]) or len(t) <= 6
    if generic_only:
        slots["theme"] = random.choice(DEFAULT_THEMES)
        return slots

    # If there's other text, use it as a creative theme (truncate)
    cleaned = raw[:64].strip()
    if cleaned:
        slots["theme"] = cleaned
    else:
        slots["theme"] = random.choice(DEFAULT_THEMES)

    return slots


def story_slots_complete(slots: dict) -> bool:
    """
    For kids, require only theme. Everything else is optional.
    """
    return bool(slots.get("theme"))


def build_story_clarifying_question(slots: dict) -> str:
    """
    One kid-friendly question.
    """
    if not slots.get("theme"):
        return (
            "Okay 😊 What should the bedtime story be about, like space, dinosaurs, animals, "
            "robots, or something else?"
        )
    if not slots.get("length"):
        return "Got it! Do you want a short story, or a longer one?"
    return "Alright… snuggle in 🌙 Your story is starting now."


def humanize_theme(theme: str) -> str:
    # if theme is one of your buckets, make it sound nicer
    mapping = {
        "space": "space and the stars",
        "dinosaurs": "dinosaurs",
        "ocean": "the ocean",
        "forest": "a cozy forest",
        "animals": "cute animals",
        "fantasy": "magic and castles",
        "robots": "friendly robots",
    }
    return mapping.get(theme, theme)

def build_story_confirmation_question(theme: str) -> str:
    return f"Okay 😊 Do you want a bedtime story about {humanize_theme(theme)}?"

def _looks_like_story_request(t: str) -> bool:
    t = (t or "").strip().lower()
    if any(trigger in t for trigger in STORY_TRIGGERS):
        # if it's basically just asking for a story with no extra content
        # treat as generic
        # examples: "i want a bedtime story", "tell me a story", "bedtime story please"
        extra = t
        for trig in STORY_TRIGGERS:
            extra = extra.replace(trig, "")
        extra = extra.strip()
        return len(extra) <= 3
    return False


def normalize_or_fallback_theme(text: str, slots: dict) -> dict:
    if slots.get("theme"):
        return slots

    raw = (text or "").strip()
    t = raw.lower()

    # ✅ expanded generic detection
    if _looks_like_story_request(t) or len(t) <= 6:
        slots["theme"] = random.choice(DEFAULT_THEMES)
        return slots

    cleaned = raw[:64].strip()
    slots["theme"] = cleaned if cleaned else random.choice(DEFAULT_THEMES)
    return slots

def looks_like_story_topic(text: str) -> bool:
    # if they mention story-related words OR there is an existing theme-like phrase
    return detect_bedtime_story_request(text)