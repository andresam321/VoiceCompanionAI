# jobs/handlers.py
"""
Job handlers for each job type.
Hardened for:
- idempotency
- short DB transactions
- trace id
- safe fallbacks
"""
from __future__ import annotations

import logging
import time
import uuid
import random
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.config import get_settings
from models.bot_profile import BotProfile
from models.conversation import Conversation
from models.interaction import Interaction

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
    if t.startswith((
        "no i mean", "no, i mean",
        "no its", "no it's",
        "no about", "no just"
    )):
        return False
    return t in {"no", "n", "nope", "nah", "different", "another"}

def extract_theme_correction(text: str) -> str | None:
    raw = (text or "").strip()
    t = raw.lower().strip()
    if not t:
        return None

    m = re.match(r"^no\b.*?\babout\b\s+(.+)$", t)
    if m:
        parts = re.split(r"\babout\b", raw, flags=re.IGNORECASE, maxsplit=1)
        remainder = parts[1].strip() if len(parts) > 1 else ""
        return remainder[:64] if remainder else None

    starters = (
        "no i mean", "no, i mean",
        "actually", "wait", "umm no", "uh no",
        "no it's", "no its", "no just",
        "no i want", "no i wan", "no i wnat",
    )
    for s in starters:
        if t.startswith(s):
            remainder = raw[len(s):].strip()
            return remainder[:64] if remainder else None
    return None

def looks_like_story_topic(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if t in {"yes", "no", "ok", "okay"}:
        return False
    return len(t.split()) <= 8


async def handle_process_voice_interaction(db: AsyncSession, payload: dict) -> dict:
    settings = get_settings()

    interaction_id = uuid.UUID(payload["interaction_id"])
    user_id = uuid.UUID(payload["user_id"])

    # Trace id per job/interaction
    trace_id = payload.get("trace_id") or uuid.uuid4().hex

    t0 = time.monotonic()

    async def checkpoint() -> None:
        """
        Commit small state updates so we don't hold a DB transaction
        during network calls. This is crucial for reliability.
        """
        await db.flush()
        await db.commit()

    logger.info("trace=%s start PROCESS_VOICE_INTERACTION interaction=%s", trace_id, interaction_id)

    # ── Load records ────────────────────────────
    interaction = await db.get(Interaction, interaction_id)
    if interaction is None:
        raise RuntimeError(f"Interaction not found: {interaction_id}")

    conversation = await db.get(Conversation, interaction.conversation_id)
    if conversation is None:
        raise RuntimeError(f"Conversation not found: {interaction.conversation_id}")

    # ── Idempotency: if already complete, return fast ─────────
    if interaction.status == "complete" and interaction.audio_output_path:
        out_path = Path(interaction.audio_output_path)
        if out_path.exists():
            logger.info("trace=%s idempotent hit, already complete", trace_id)
            return {"interaction_id": str(interaction_id), "latency_ms": interaction.latency_ms or 0, "idempotent": True}

    # mark processing
    interaction.status = "processing"
    await checkpoint()

    # ── Transcript (idempotent) ─────────────────
    if interaction.transcript and interaction.transcript.strip():
        transcript = interaction.transcript.strip()
    else:
        # Commit before network call
        await checkpoint()
        transcript = await transcribe_audio(interaction.audio_input_path)
        interaction.transcript = transcript
        await checkpoint()

    # ── Emotion (best-effort, don't fail job) ───
    try:
        if interaction.audio_input_path:
            await checkpoint()
            emotion = await detect_emotion(interaction.audio_input_path, transcript)
            interaction.detected_emotion = emotion.label
            interaction.emotion_confidence = emotion.confidence
            await checkpoint()
    except Exception as exc:
        logger.warning("trace=%s emotion detection failed: %s", trace_id, exc)

    # ── Routing setup ───────────────────────────
    goto_llm = True
    assistant_reply: str | None = None
    bot_profile = (
    await db.execute(
        select(BotProfile)
        .where(BotProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    bot_name = bot_profile.name if bot_profile and bot_profile.name else "Buddy"

    system_prompt = (
        f"You are a friendly, playful companion for a child. "
        f"Your name is {bot_name}. "
        f"If the child asks your name, say: 'My name is {bot_name}!'. "
        "Keep replies short, warm, and engaging."
    )

    # ==========================================================
    # STORY INTENT LOOP (no LLM for clarifying questions)
    # ==========================================================
    if conversation.pending_intent == STORY_INTENT:
        slots: dict[str, Any] = conversation.pending_slots or {}
        text = transcript.strip()

        if slots.get("awaiting_confirmation"):
            correction = extract_theme_correction(text)

            if correction:
                merged = dict(slots)
                merged["theme"] = correction[:64]
                merged["awaiting_confirmation"] = True
                conversation.pending_slots = merged
                await checkpoint()

                assistant_reply = build_story_confirmation_question(merged["theme"])
                goto_llm = False

            elif is_affirmative(text):
                theme = slots.get("theme", "a cozy adventure")
                length = slots.get("length", "short")

                conversation.pending_intent = None
                conversation.pending_slots = None
                await checkpoint()

                transcript = (
                    "Tell a calming bedtime story for a child.\n"
                    f"Theme: {theme}\n"
                    f"Length: {length}\n"
                    "Keep it gentle and cozy.\n"
                    "End with a goodnight message."
                )
                system_prompt = "You are a warm bedtime storyteller for children."
                goto_llm = True

            elif is_negative(text):
                conversation.pending_slots = {"awaiting_confirmation": False}
                await checkpoint()

                assistant_reply = "Okay 😊 What should the bedtime story be about instead?"
                goto_llm = False

            else:
                if looks_like_story_topic(text):
                    new_slots = extract_story_slots(text)
                    merged = {**slots, **new_slots}
                    merged = normalize_or_fallback_theme(text, merged)
                    merged["awaiting_confirmation"] = True
                    conversation.pending_slots = merged
                    await checkpoint()

                    assistant_reply = build_story_confirmation_question(merged["theme"])
                    goto_llm = False
                else:
                    assistant_reply = build_story_confirmation_question(slots.get("theme", "that idea"))
                    goto_llm = False

        else:
            new_slots = extract_story_slots(text)
            merged = {**(slots or {}), **new_slots}
            merged = normalize_or_fallback_theme(text, merged)

            if not story_slots_complete(merged):
                conversation.pending_slots = merged
                await checkpoint()
                assistant_reply = build_story_clarifying_question(merged)
                goto_llm = False
            else:
                merged["awaiting_confirmation"] = True
                conversation.pending_slots = merged
                await checkpoint()
                assistant_reply = build_story_confirmation_question(merged["theme"])
                goto_llm = False

    # ==========================================================
    # NEW STORY REQUEST
    # ==========================================================
    else:
        if detect_bedtime_story_request(transcript):
            slots = extract_story_slots(transcript)

            if not slots.get("theme"):
                favorites = await get_favorite_characters(db, user_id)
                if favorites:
                    slots["theme"] = random.choice(favorites)
                else:
                    slots = normalize_or_fallback_theme(transcript, slots)

            slots["awaiting_confirmation"] = True
            conversation.pending_intent = STORY_INTENT
            conversation.pending_slots = slots
            await checkpoint()

            assistant_reply = build_story_confirmation_question(slots["theme"])
            goto_llm = False

    # ==========================================================
    # LLM (idempotent + fallback)
    # ==========================================================
    # Idempotency: if we already generated assistant reply earlier, skip LLM
    if interaction.assistant_reply and interaction.assistant_reply.strip():
        assistant_reply = interaction.assistant_reply.strip()
        goto_llm = False

    if goto_llm:
        try:
            await checkpoint()
            assistant_reply = await chat_completion(system_prompt, transcript)
        except Exception as exc:
            logger.error("trace=%s llm failed: %s", trace_id, exc)
            assistant_reply = "Hmm, I’m thinking really hard 😊 Can you tell me again?"

    if not assistant_reply:
        assistant_reply = "Okay 😊 What should we do next?"

    interaction.assistant_reply = assistant_reply
    await checkpoint()

    # ── TTS (idempotent + best-effort) ──────────
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    audio_out = settings.audio_dir / f"{interaction_id}.wav"

    # If audio already exists and path matches, skip regeneration
    if interaction.audio_output_path:
        existing = Path(interaction.audio_output_path)
        if existing.exists():
            audio_out = existing

    if not audio_out.exists():

        voice = (
            bot_profile.voice
            if bot_profile and bot_profile.voice
            else settings.openai_tts_voice
        )

        try:
            await checkpoint()
            await synthesize_speech(assistant_reply, audio_out, voice=voice)
        except Exception as exc:
            # Do NOT brick the interaction for a kid, keep text reply
            logger.error("trace=%s tts failed: %s", trace_id, exc)

    interaction.audio_output_path = str(audio_out)

    # ── finalize ────────────────────────────────
    interaction.latency_ms = int((time.monotonic() - t0) * 1000)
    interaction.status = "complete"
    await checkpoint()

    logger.info("trace=%s complete interaction=%s latency_ms=%s", trace_id, interaction_id, interaction.latency_ms)

    return {
        "interaction_id": str(interaction_id),
        "latency_ms": interaction.latency_ms,
        "trace_id": trace_id,
    }


async def handle_summarize_profile(db: AsyncSession, payload: dict) -> dict:
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

    try:
        summary = await chat_completion("Summarize this child's personality.", text_blob)
    except Exception:
        summary = "I’m still learning what you like, but I love stories and fun games!"

    return {"summary": summary}


HANDLERS = {
    "PROCESS_VOICE_INTERACTION": handle_process_voice_interaction,
    "SUMMARIZE_PROFILE": handle_summarize_profile,
}