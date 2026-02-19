# services/openai_embeddings.py
from __future__ import annotations

import logging

from openai import AsyncOpenAI

from api.app.config import get_settings

logger = logging.getLogger(__name__)


async def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for a piece of text."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    logger.info("Embedding: generating for %d chars", len(text))
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )
    return response.data[0].embedding
