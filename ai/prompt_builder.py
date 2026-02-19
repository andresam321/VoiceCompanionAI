# ai/prompt_builder.py
"""
Assembles a layered system prompt from personality, safety, mode,
bot profile traits, memories, user profile, and emotional context.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ai.prompts.system_buddy import SYSTEM_BUDDY
from ai.prompts.safety_kid import SAFETY_KID
from ai.prompts.modes import MODES


@dataclass
class PromptContext:
    bot_name: str = "Robot"
    warmth: float = 0.9
    humor: float = 0.7
    curiosity: float = 0.8
    energy: float = 0.6
    verbosity: float = 0.4
    max_sentences: int = 4
    active_mode: str = "default"
    safety_enabled: bool = True
    memories: list[str] = field(default_factory=list)
    user_profile_summary: str | None = None
    detected_emotion: str | None = None
    emotion_confidence: float | None = None


def build_system_prompt(ctx: PromptContext) -> str:
    """Build the full system prompt from all layers."""
    sections: list[str] = []

    # 1. Core personality
    personality = SYSTEM_BUDDY.format(
        bot_name=ctx.bot_name,
        warmth=ctx.warmth,
        humor=ctx.humor,
        curiosity=ctx.curiosity,
        energy=ctx.energy,
        verbosity=ctx.verbosity,
        max_sentences=ctx.max_sentences,
    )
    sections.append(personality)

    # 2. Safety layer
    if ctx.safety_enabled:
        sections.append(SAFETY_KID)

    # 3. Mode overlay
    mode_text = MODES.get(ctx.active_mode, "")
    if mode_text:
        sections.append(mode_text)

    # 4. User profile
    if ctx.user_profile_summary:
        sections.append(
            f"ABOUT THE PERSON YOU'RE TALKING TO:\n{ctx.user_profile_summary}"
        )

    # 5. Relevant memories
    if ctx.memories:
        memory_block = "THINGS YOU REMEMBER:\n" + "\n".join(
            f"- {m}" for m in ctx.memories
        )
        sections.append(memory_block)

    # 6. Emotional tone injection
    if ctx.detected_emotion and ctx.detected_emotion != "neutral":
        conf = ctx.emotion_confidence or 0.5
        sections.append(
            f"EMOTIONAL CONTEXT: The person seems {ctx.detected_emotion} "
            f"(confidence: {conf:.0%}). Adapt your tone accordingly."
        )

    return "\n\n".join(sections)
