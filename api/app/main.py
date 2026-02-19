# api/app/main.py
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.config import get_settings
from api.app.routes import audio, bot_profile, health, voice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Companion API",
    description="Conversational AI companion orchestrator",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(voice.router, prefix="/v1")
app.include_router(audio.router, prefix="/v1")
app.include_router(bot_profile.router, prefix="/v1")
