# api/app/routes/voice.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.config import get_settings
from api.app.dependencies import get_current_user, get_session
from api.app.schemas.voice import InteractionDetail, VoiceInteractionResponse
from jobs.queue import enqueue
from models.conversation import Conversation
from models.interaction import Interaction
from models.user import User
from services.observability import log_event
from api.app.schemas.dev_voice import DevVoiceRequest  # add import

router = APIRouter(tags=["voice"])



@router.post("/voice-interactions/dev", response_model=VoiceInteractionResponse)
async def create_dev_voice_interaction(
    body: DevVoiceRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """
    DEV ONLY: Create an interaction from a provided transcript (no audio upload).
    Lets you test full back-and-forth without STT/TTS wired.
    """
    # Get or create active conversation
    if body.conversation_id:
        stmt = select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation is None:
            conversation = Conversation(user_id=user.id, title="New conversation")
            db.add(conversation)
            await db.flush()

    # Create interaction with transcript already set
    interaction_id = uuid.uuid4()
    interaction = Interaction(
        id=interaction_id,
        conversation_id=conversation.id,
        user_id=user.id,
        transcript=body.transcript,
        status="pending",
    )
    db.add(interaction)
    await db.flush()

    # Enqueue job (same as real voice path)
    await enqueue(db, "PROCESS_VOICE_INTERACTION", {
        "interaction_id": str(interaction.id),
        "user_id": str(user.id),
        "conversation_id": str(conversation.id),
        "dev_mode": True,  # optional flag (worker can ignore)
    })

    await log_event(db, "dev_voice_interaction_created", "info", source="api", metadata={
        "interaction_id": str(interaction.id),
        "conversation_id": str(conversation.id),
    })

    return VoiceInteractionResponse(
        interaction_id=interaction.id,
        conversation_id=conversation.id,
        status="pending",
        message="Dev transcript received. Processing queued.",
    )

@router.post("/voice-interactions", response_model=VoiceInteractionResponse)
async def create_voice_interaction(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Upload audio, create an interaction, and enqueue processing."""
    settings = get_settings()

    # Get or create active conversation
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        conversation = Conversation(user_id=user.id, title="New conversation")
        db.add(conversation)
        await db.flush()

    # Save uploaded audio
    interaction_id = uuid.uuid4()

    settings.audio_dir.mkdir(parents=True, exist_ok=True)  # ✅ make sure it exists
    audio_path = settings.audio_dir / f"input_{interaction_id}.wav"

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    audio_path.write_bytes(content)

    # Create interaction row
    interaction = Interaction(
        id=interaction_id,
        conversation_id=conversation.id,
        user_id=user.id,
        audio_input_path=str(audio_path),
        status="pending",
    )
    db.add(interaction)
    await db.flush()

    # Enqueue job
    await enqueue(
        db,
        "PROCESS_VOICE_INTERACTION",
        {
            "interaction_id": str(interaction.id),
            "user_id": str(user.id),
            "conversation_id": str(conversation.id),
        },
    )

    await log_event(
        db,
        "voice_interaction_created",
        "info",
        source="api",
        metadata={"interaction_id": str(interaction.id)},
    )

    return VoiceInteractionResponse(
        interaction_id=interaction.id,
        conversation_id=conversation.id,
        status=interaction.status,
        message="Audio received. Processing queued.",
    )


@router.get("/voice-interactions/{interaction_id}", response_model=InteractionDetail)
async def get_voice_interaction(
    interaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Poll a specific interaction by id (recommended)."""
    stmt = select(Interaction).where(
        Interaction.id == interaction_id,
        Interaction.user_id == user.id,
    )
    result = await db.execute(stmt)
    interaction = result.scalar_one_or_none()
    if interaction is None:
        raise HTTPException(status_code=404, detail="Interaction not found")

    return InteractionDetail.model_validate(interaction)


@router.get("/interactions/latest", response_model=InteractionDetail)
async def get_latest_interaction(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Legacy polling (ok for MVP, but less reliable)."""
    stmt = (
        select(Interaction)
        .where(Interaction.user_id == user.id)
        .order_by(Interaction.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    interaction = result.scalar_one_or_none()

    if interaction is None:
        raise HTTPException(status_code=404, detail="No interactions found")

    return InteractionDetail.model_validate(interaction)
