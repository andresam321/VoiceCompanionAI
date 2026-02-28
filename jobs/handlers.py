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
from services.memory_service import retrieve_relevant_memories, extract_memories, store_memory
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
    if not t:
        return False

    # exact quick matches
    if t in {"yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay"}:
        return True

    # prefix matches for natural speech
    return (
        t.startswith("yes")
        or t.startswith("yeah")
        or t.startswith("yep")
        or t.startswith("yup")
        or t.startswith("sure")
        or t.startswith("ok")
        or t.startswith("okay")
        or "let's do it" in t
        or "do it" in t
        or "go ahead" in t
        or "start" in t
    )

def is_cancel(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(p in t for p in (
        "cancel", "stop", "exit", "quit",
        "never mind", "nevermind",
        "no story", "not a story",
        "dont tell a story", "don't tell a story",
        "don't want a story", "dont want a story",
    ))

def is_plain_no(text: str) -> bool:
    t = (text or "").strip().lower()
    if t in {"no", "nope", "nah", "n"}:
        return True
    # treat "no ..." as a no (unless it's a correction like "no, about dinosaurs")
    return t.startswith("no ") or t.startswith("no,")

def extract_theme_correction(text: str) -> str | None:
    raw = (text or "").strip()
    t = raw.lower().strip()
    if not t:
        return None

    # common "no, about X" or "no about X"
    m = re.match(r"^no\b.*?\babout\b\s+(.+)$", t)
    if m:
        return m.group(1).strip()[:64] or None

    # "no i want X", "no i want it to be X", "no make it X"
    m = re.match(r"^no\b[\s,]*?(?:i\s+want|i\s+want\s+it\s+to\s+be|make\s+it|do\s+it|let's\s+do)\s+(.+)$", t)
    if m:
        return m.group(1).strip()[:64] or None

    # "actually X", "wait X"
    m = re.match(r"^(?:actually|wait)[\s,]+(.+)$", t)
    if m:
        return m.group(1).strip()[:64] or None

    return None

def looks_like_story_topic(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if t in {"yes", "no", "ok", "okay"}:
        return False
    return len(t.split()) <= 8


async def build_conversation_history(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    interaction_id: uuid.UUID,
    limit: int = 12,
) -> list[dict]:
    stmt = (
        select(Interaction)
        .where(
            Interaction.conversation_id == conversation_id,
            Interaction.id != interaction_id,  # don’t include current turn
        )
        .order_by(Interaction.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    rows = list(reversed(rows))  # chronological

    history: list[dict] = []
    for it in rows:
        if it.transcript and it.transcript.strip():
            history.append({"role": "user", "content": it.transcript.strip()})
        if it.assistant_reply and it.assistant_reply.strip():
            history.append({"role": "assistant", "content": it.assistant_reply.strip()})
    return history

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
            return {
                "interaction_id": str(interaction_id),
                "latency_ms": interaction.latency_ms or 0,
                "idempotent": True,
            }

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
        await db.execute(select(BotProfile).where(BotProfile.user_id == user_id))
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

        # Allow explicit cancel at any point in story flow
        if is_cancel(text):
            conversation.pending_intent = None
            conversation.pending_slots = None
            await checkpoint()

            assistant_reply = "Okay 😊 No story. What do you want to do instead?"
            goto_llm = False

        elif slots.get("awaiting_confirmation"):
            # loop breaker counter
            slots.setdefault("no_count", 0)

            correction = extract_theme_correction(text)

            if correction:
                merged = dict(slots)
                merged["theme"] = correction[:64]
                merged["awaiting_confirmation"] = True
                merged["no_count"] = 0
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

            elif is_plain_no(text):
                merged = dict(slots)
                merged["no_count"] = int(merged.get("no_count", 0)) + 1

                if merged["no_count"] >= 2:
                    # Second plain "no" -> exit story mode
                    conversation.pending_intent = None
                    conversation.pending_slots = None
                    await checkpoint()

                    assistant_reply = "Okay We can stop. What do you want to do next?"
                    goto_llm = False
                else:
                    # First plain "no" -> revise theme (ask for a new topic)
                    merged["awaiting_confirmation"] = False
                    conversation.pending_slots = merged
                    await checkpoint()

                    assistant_reply = "Okay What should the bedtime story be about instead?"
                    goto_llm = False

            else:
                # If kid says a short topic, treat it as new theme and reconfirm
                if looks_like_story_topic(text):
                    new_slots = extract_story_slots(text)
                    merged = {**slots, **new_slots}
                    merged = normalize_or_fallback_theme(text, merged)
                    merged["awaiting_confirmation"] = True
                    merged["no_count"] = 0
                    conversation.pending_slots = merged
                    await checkpoint()

                    assistant_reply = build_story_confirmation_question(merged["theme"])
                    goto_llm = False
                else:
                    assistant_reply = build_story_confirmation_question(slots.get("theme", "that idea"))
                    goto_llm = False

        else:
            # awaiting_confirmation is False -> gather slots
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
                merged.setdefault("no_count", 0)
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
            slots["no_count"] = 0
            conversation.pending_intent = STORY_INTENT
            conversation.pending_slots = slots
            await checkpoint()

            assistant_reply = build_story_confirmation_question(slots["theme"])
            goto_llm = False

    # ==========================================================
    # LLM (idempotent + fallback)
    # ==========================================================
    if goto_llm:
        try:
            await checkpoint()

            # short-term context (last turns)
            history = await build_conversation_history(
                db=db,
                conversation_id=conversation.id,
                interaction_id=interaction.id,
                limit=12,
            )

            # long-term context (personalization)
            mems = await retrieve_relevant_memories(
                db,
                user_id,
                transcript,
                limit=5,
            )

            if mems:
                memory_block = "Helpful facts about the child:\n" + "\n".join(
                    f"- {m.content}" for m in mems
                )
                conversation_history = [{"role": "system", "content": memory_block}] + history
            else:
                conversation_history = history

            assistant_reply = await chat_completion(
                system_prompt=system_prompt,
                user_message=transcript,
                conversation_history=conversation_history,
            )

        except Exception as exc:
            logger.error("trace=%s llm failed: %s", trace_id, exc)
            assistant_reply = "Hmm, I’m thinking really hard 😊 Can you tell me again?"

    if not assistant_reply:
        assistant_reply = "Okay What should we do next?"

    interaction.assistant_reply = assistant_reply
    # await checkpoint()
    # ── Long-term memory write (best-effort) ───────
    try:
        await checkpoint()  # end any open transaction before network calls

        memories = await extract_memories(
            transcript=transcript,
            assistant_reply=assistant_reply,
            detected_emotion=getattr(interaction, "detected_emotion", None),
        )

        for m in memories:
            content = (m.get("content") or "").strip()
            if not content:
                continue

            salience = float(m.get("salience", 0.5) or 0.5)

            # guardrails to avoid memory pollution
            if salience < 0.6:
                continue
            if len(content) < 6:
                continue

            await store_memory(
                db=db,
                user_id=user_id,
                interaction_id=interaction.id,
                content=content[:500],  # keep it compact
                category=m.get("category") or "general",
                emotional_context=m.get("emotional_context"),
                salience_score=salience,
            )

        await checkpoint()
    except Exception as exc:
        logger.warning("trace=%s memory write skipped: %s", trace_id, exc)

    # ── TTS (idempotent + best-effort) ──────────
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    audio_out = settings.audio_dir / f"{interaction_id}.wav"

    # If audio already exists and path matches, skip regeneration
    if interaction.audio_output_path:
        existing = Path(interaction.audio_output_path)
        if existing.exists():
            audio_out = existing

    if not audio_out.exists():
        voice = bot_profile.voice if bot_profile and bot_profile.voice else settings.openai_tts_voice

        try:
            await checkpoint()
            await synthesize_speech(assistant_reply, audio_out, voice=voice)
        except Exception as exc:
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
