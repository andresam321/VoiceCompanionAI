# api/app/schemas/bot_profile.py
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class BotProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    voice: str
    traits: dict
    rules: dict
    favorite_modes: list
    active_mode: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BotProfileUpdate(BaseModel):
    name: str | None = None
    voice: str | None = None
    traits: dict | None = None
    rules: dict | None = None
    favorite_modes: list | None = None
    active_mode: str | None = None
