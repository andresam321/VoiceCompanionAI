# api/app/config.py
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application configuration.

    Loads environment variables from `.env` and provides
    typed access across API, worker, and services.
    """

    # ─────────────────────────────────────────────
    # Pydantic Settings Config
    # ─────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────
    database_url: str
    database_url_sync: str | None = None

    # ─────────────────────────────────────────────
    # OpenAI
    # ─────────────────────────────────────────────
    openai_api_key: str
    openai_model: str = "gpt-4o"

    openai_tts_model: str = "tts-1"
    openai_tts_voice: str = "nova"

    openai_stt_model: str = "whisper-1"
    openai_embedding_model: str = "text-embedding-3-small"

    # ─────────────────────────────────────────────
    # API
    # ─────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str

    # ─────────────────────────────────────────────
    # Device Agent
    # ─────────────────────────────────────────────
    api_base_url: str = "http://localhost:8000"
    device_token: str | None = None

    # ─────────────────────────────────────────────
    # Audio Storage
    # ─────────────────────────────────────────────
    audio_storage_path: str = "/data/audio"

    # ─────────────────────────────────────────────
    # Worker
    # ─────────────────────────────────────────────
    worker_poll_interval: float = 1.0
    worker_max_retries: int = 3

    # ─────────────────────────────────────────────
    # Derived Properties
    # ─────────────────────────────────────────────
    @property
    def audio_dir(self) -> Path:
        """
        Ensures audio storage directory exists
        and returns Path object.
        """
        p = Path(self.audio_storage_path)
        p.mkdir(parents=True, exist_ok=True)
        return p


# ─────────────────────────────────────────────
# Cached Settings Instance
# ─────────────────────────────────────────────
@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance so config
    is only loaded once per process.
    """
    return Settings()
