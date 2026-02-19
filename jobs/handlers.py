# jobs/handlers.py
"""
Job handlers for each job type.
"""
from __future__ import annotations

import logging
import time
import uuid
import random
from typing import Any

import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.config import get_settings
from models.bot_profile import BotProfile
from models.conversation import Conversation
from models.interaction import Interaction
from models.user_profile import UserProfile

from services.favorite_characters import get_favorite_characters
from services.emotion_detector import detect_emotion
from services.memory_service import retrieve_relevant_memories
from services.openai_llm import chat_completion
from services.openai_stt import transcribe_audio
from services.openai_tts import synthesize_speech

from ai.intents.story import (
    STORY_INTENT,
    detect_bedtime_story_request,
    extract_story_slots,
    normalize_or_fallback_theme,
    story_slots_complete,
    build_story_clarifying_question,
    build_story_confirmation_question,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────

def is_affirmative(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {
        "yes", "y", "yeah", "yep", "yup",
        "ok", "okay", "sure", "please",
        "do it", "yes please", "ok please"
    }

def is_negative(text: str) -> bool:
    t = (text or "").strip().lower()

    # Don't treat corrections as pure "no"
    if t.startswith((
        "no i mean", "no, i mean",
        "no its", "no it's",
        "no about", "no just"
    )):
        return False

    return t in {"no", "n", "nope", "nah", "different", "another"}


def extract_theme_correction(text: str) -> str | None:
    """
    Catches kid corrections like:
      - "no i mean bluey"
      - "no i want it about spiderman and bluey"
      - "no about robots"
      - "actually dinosaurs"
      - "wait pizza moon robot"
    Returns corrected theme snippet or None.
    """
    raw = (text or "").strip()
    t = raw.lower().strip()
    if not t:
        return None

    # 1) Very common correction patterns (typo-tolerant)
    # "no i want/wan/wnat it about X", "no about X"
    m = re.match(r"^no\b.*?\babout\b\s+(.+)$", t)
    if m:
        # slice from original raw using matched group length is annoying,
        # just return from lower match but keep original-ish by using raw split
        # simple: split on 'about' from raw
        parts = re.split(r"\babout\b", raw, flags=re.IGNORECASE, maxsplit=1)
        remainder = parts[1].strip() if len(parts) > 1 else ""
        return remainder[:64] if remainder else None

    # 2) Starters like "no i mean", "actually", "wait"
    starters = (
        "no i mean", "no, i mean",
        "actually", "wait", "umm no", "uh no",
        "no it's", "no its", "no just",
        "no i want", "no i wan", "no i wnat",  # include typos
    )
    for s in starters:
        if t.startswith(s):
            remainder = raw[len(s):].strip()
            return remainder[:64] if remainder else None

    return None

def clean_theme_text(text: str) -> str:
    fillers = ["it", "about", "story", "a story", "the story"]
    cleaned = text.lower()
    for f in fillers:
        cleaned = cleaned.replace(f, "")
    return cleaned.strip()[:64]

def looks_like_story_topic(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if t in {"yes", "no", "ok", "okay"}:
        return False
    return len(t.split()) <= 8

# ─────────────────────────────────────────────
# MAIN HANDLER
# ─────────────────────────────────────────────

async def handle_process_voice_interaction(
    db: AsyncSession,
    payload: dict
) -> dict:

    settings = get_settings()

    interaction_id = uuid.UUID(payload["interaction_id"])
    user_id = uuid.UUID(payload["user_id"])
    t0 = time.monotonic()

    async def save_state():
        await db.flush()
        await db.commit()

    # ── Load records ────────────────────────────
    interaction = await db.get(Interaction, interaction_id)
    conversation = await db.get(Conversation, interaction.conversation_id)

    interaction.status = "processing"
    await save_state()

    # ── Transcript ──────────────────────────────
    if interaction.transcript:
        transcript = interaction.transcript.strip()
    else:
        transcript = await transcribe_audio(interaction.audio_input_path)
        interaction.transcript = transcript
        await db.flush()

    # ── Emotion ─────────────────────────────────
    if interaction.audio_input_path:
        emotion = await detect_emotion(
            interaction.audio_input_path,
            transcript
        )
        interaction.detected_emotion = emotion.label
        interaction.emotion_confidence = emotion.confidence

    await db.flush()

    # ── Routing setup ───────────────────────────
    goto_llm = True
    assistant_reply: str | None = None

    system_prompt = (
        "You are a friendly, playful companion for a child. "
        "Keep replies short, warm, and engaging."
    )

    # ==========================================================
    # STORY INTENT LOOP
    # ==========================================================
    if conversation.pending_intent == STORY_INTENT:

        slots: dict[str, Any] = conversation.pending_slots or {}
        text = transcript.strip()

        # ── awaiting confirmation ─────────────────
        if slots.get("awaiting_confirmation"):

            correction = extract_theme_correction(text)

            if correction:
                merged = dict(slots)
                merged["theme"] = correction[:64]
                merged["awaiting_confirmation"] = True

                conversation.pending_slots = merged
                await save_state()

                assistant_reply = (
                    build_story_confirmation_question(
                        merged["theme"]
                    )
                )
                goto_llm = False

            elif is_affirmative(text):

                theme = slots.get("theme", "a cozy adventure")
                length = slots.get("length", "short")

                conversation.pending_intent = None
                conversation.pending_slots = None
                await save_state()

                transcript = (
                    "Tell a calming bedtime story for a child.\n"
                    f"Theme: {theme}\n"
                    f"Length: {length}\n"
                    "Keep it gentle and cozy.\n"
                    "End with a goodnight message."
                )

                system_prompt = (
                    "You are a warm bedtime storyteller for children."
                )
                goto_llm = True

            elif is_negative(text):

                conversation.pending_slots = {
                    "awaiting_confirmation": False
                }
                await save_state()

                assistant_reply = (
                    "Okay 😊 What should the bedtime story be about instead?"
                )
                goto_llm = False

            else:

                if looks_like_story_topic(text):

                    new_slots = extract_story_slots(text)
                    merged = {**slots, **new_slots}
                    merged = normalize_or_fallback_theme(
                        text, merged
                    )

                    merged["awaiting_confirmation"] = True
                    conversation.pending_slots = merged
                    await save_state()

                    assistant_reply = (
                        build_story_confirmation_question(
                            merged["theme"]
                        )
                    )
                    goto_llm = False

                else:
                    assistant_reply = (
                        build_story_confirmation_question(
                            slots.get("theme", "that idea")
                        )
                    )
                    goto_llm = False

        # ── theme gathering ───────────────────────
        else:

            new_slots = extract_story_slots(text)
            merged = {**slots, **new_slots}
            merged = normalize_or_fallback_theme(text, merged)

            if not story_slots_complete(merged):

                conversation.pending_slots = merged
                await save_state()

                assistant_reply = (
                    build_story_clarifying_question(merged)
                )
                goto_llm = False

            else:

                merged["awaiting_confirmation"] = True
                conversation.pending_slots = merged
                await save_state()

                assistant_reply = (
                    build_story_confirmation_question(
                        merged["theme"]
                    )
                )
                goto_llm = False

    # ==========================================================
    # NEW STORY REQUEST
    # ==========================================================
    else:

        if detect_bedtime_story_request(transcript):

            slots = extract_story_slots(transcript)

            if not slots.get("theme"):
                favorites = await get_favorite_characters(
                    db, user_id
                )

                if favorites:
                    slots["theme"] = random.choice(favorites)
                else:
                    slots = normalize_or_fallback_theme(
                        transcript, slots
                    )

            slots["awaiting_confirmation"] = True

            conversation.pending_intent = STORY_INTENT
            conversation.pending_slots = slots
            await save_state()

            assistant_reply = (
                build_story_confirmation_question(
                    slots["theme"]
                )
            )
            goto_llm = False

    # ==========================================================
    # LLM
    # ==========================================================
    if goto_llm:
        assistant_reply = await chat_completion(
            system_prompt,
            transcript
        )

    if not assistant_reply:
        assistant_reply = "Okay 😊 What should we do next?"

    interaction.assistant_reply = assistant_reply
    await db.flush()

    # ── TTS ─────────────────────────────────────
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    audio_out = settings.audio_dir / f"{interaction_id}.wav"

    bot_profile = (
        await db.execute(
            select(BotProfile)
            .where(BotProfile.user_id == user_id)
        )
    ).scalar_one_or_none()

    voice = (
        bot_profile.voice
        if bot_profile and bot_profile.voice
        else settings.openai_tts_voice
    )

    await synthesize_speech(
        assistant_reply,
        audio_out,
        voice=voice
    )

    interaction.audio_output_path = str(audio_out)

    # ── finalize ────────────────────────────────
    interaction.latency_ms = int(
        (time.monotonic() - t0) * 1000
    )
    interaction.status = "complete"

    await save_state()

    return {
        "interaction_id": str(interaction_id),
        "latency_ms": interaction.latency_ms,
    }

# ==========================================================
# OTHER JOBS
# ==========================================================

async def handle_summarize_profile(
    db: AsyncSession,
    payload: dict
) -> dict:

    user_id = uuid.UUID(payload["user_id"])

    memories = await retrieve_relevant_memories(
        db,
        user_id,
        "general preferences",
        limit=20,
    )

    if not memories:
        return {"status": "no_memories"}

    text_blob = "\n".join(m.content for m in memories)

    summary = await chat_completion(
        "Summarize this child's personality.",
        text_blob,
    )

    return {"summary": summary}

# ==========================================================
# REGISTRY
# ==========================================================

HANDLERS = {
    "PROCESS_VOICE_INTERACTION": handle_process_voice_interaction,
    "SUMMARIZE_PROFILE": handle_summarize_profile,
}
