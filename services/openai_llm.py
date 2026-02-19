# services/openai_llm.py
from __future__ import annotations

import logging

from openai import AsyncOpenAI

from api.app.config import get_settings

logger = logging.getLogger(__name__)


async def chat_completion(
    system_prompt: str,
    user_message: str,
    conversation_history: list[dict] | None = None,
    temperature: float = 0.8,
    max_tokens: int = 512,
) -> str:
    """Run an LLM chat completion and return the assistant message text."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    logger.info("LLM: sending %d messages to %s", len(messages), settings.openai_model)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = response.choices[0].message.content or ""
    logger.info("LLM: got %d chars response", len(text))
    return text


async def extract_json(system_prompt: str, user_message: str) -> str:
    """Run a completion expecting JSON output (for memory extraction, etc.)."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"
