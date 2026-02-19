# api/app/schemas/dev_voice.py
from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class DevVoiceRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
