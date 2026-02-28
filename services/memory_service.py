# services/memory_service.py
"""
Memory service: extract, embed, store, and retrieve long-term memories.
"""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.memory import Memory
from models.memory_embedding import MemoryEmbedding
from services.openai_embeddings import generate_embedding
from services.openai_llm import extract_json

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a memory extractor for a conversational AI companion.
Given the user's message and the assistant's reply, extract facts, preferences,
events, or emotional states worth remembering long-term.

Respond with JSON:
{
  "memories": [
    {
      "content": "...",
      "category": "preference|fact|emotion|event",
      "emotional_context": "happy|sad|neutral|...",
      "salience": 0.0-1.0
    }
  ]
}

If there is nothing worth remembering, return {"memories": []}.
"""

def rule_based_memory_candidates(text: str) -> list[str]:
    t = text.lower().strip()
    memories = []

    if t.startswith("i like "):
        memories.append(f"Likes {text[7:].strip()}")
    elif t.startswith("i love "):
        memories.append(f"Loves {text[7:].strip()}")
    elif t.startswith("my favorite"):
        memories.append(text.strip())
    elif t.startswith("i don't like") or t.startswith("i dont like"):
        memories.append(text.strip())
    elif "my dog's name is" in t or "my dog is named" in t:
        memories.append(text.strip())
    elif t.startswith("i am scared of") or "i'm scared of" in t:
        memories.append(text.strip())

    return memories

async def extract_memories(
    transcript: str,
    assistant_reply: str,
    detected_emotion: str | None = None,
) -> list[dict]:
    """Use LLM to extract memorable facts from an interaction."""
    user_input = (
        f"User said: {transcript}\n"
        f"Assistant replied: {assistant_reply}\n"
        f"Detected emotion: {detected_emotion or 'unknown'}"
    )
    try:
        raw = await extract_json(EXTRACTION_PROMPT, user_input)
        data = json.loads(raw)
        memories = data.get("memories", [])
        logger.info("Extracted %d memories", len(memories))
        return memories
    except Exception as exc:
        logger.error("Memory extraction failed: %s", exc)
        return []


async def store_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    interaction_id: uuid.UUID | None,
    content: str,
    category: str = "general",
    emotional_context: str | None = None,
    salience_score: float = 0.5,
) -> Memory:
    """Store a memory and its embedding."""
    memory = Memory(
        user_id=user_id,
        interaction_id=interaction_id,
        content=content,
        category=category,
        emotional_context=emotional_context,
        salience_score=salience_score,
    )
    db.add(memory)
    await db.flush()

    # Generate and store embedding
    try:
        vector = await generate_embedding(content)
        emb = MemoryEmbedding(memory_id=memory.id, embedding=vector)
        db.add(emb)
        await db.flush()
    except Exception as exc:
        logger.warning("Embedding generation failed for memory %s: %s", memory.id, exc)

    return memory


async def retrieve_relevant_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    limit: int = 5,
) -> list[Memory]:
    """Retrieve the most relevant memories using cosine similarity on pgvector."""
    try:
        query_embedding = await generate_embedding(query)
    except Exception as exc:
        logger.warning("Query embedding failed: %s", exc)
        # Fallback: return most recent salient memories
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.salience_score.desc(), Memory.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # pgvector cosine distance search
    stmt = (
        select(Memory)
        .join(MemoryEmbedding, MemoryEmbedding.memory_id == Memory.id)
        .where(Memory.user_id == user_id)
        .order_by(
            MemoryEmbedding.embedding.cosine_distance(query_embedding)
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
