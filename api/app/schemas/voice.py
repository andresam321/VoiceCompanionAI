# api/app/schemas/voice.py
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class VoiceInteractionResponse(BaseModel):
    interaction_id: uuid.UUID
    conversation_id: uuid.UUID
    status: str
    message: str


class InteractionDetail(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    status: str
    transcript: str | None = None
    assistant_reply: str | None = None
    detected_emotion: str | None = None
    emotion_confidence: float | None = None
    latency_ms: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
