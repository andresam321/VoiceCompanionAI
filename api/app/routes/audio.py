# api/app/routes/audio.py
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.dependencies import get_current_user, get_session
from models.interaction import Interaction
from models.user import User

router = APIRouter(tags=["audio"])


@router.get("/audio/{interaction_id}.wav")
async def get_audio(
    interaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Retrieve TTS audio for a completed interaction."""
    interaction = await db.get(Interaction, interaction_id)

    if interaction is None or interaction.user_id != user.id:
        raise HTTPException(status_code=404, detail="Interaction not found")

    if interaction.status != "complete" or not interaction.audio_output_path:
        raise HTTPException(status_code=404, detail="Audio not yet available")

    audio_path = Path(interaction.audio_output_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing")

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"{interaction_id}.wav",
    )
