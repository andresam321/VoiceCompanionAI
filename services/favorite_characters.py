# services/favorite_characters.py

from services.memory_service import retrieve_relevant_memories

CHARACTER_HINTS = [
    "bluey",
    "elsa",
    "spiderman",
    "mario",
    "sonic",
    "peppa pig",
]

async def get_favorite_characters(db, user_id):
    memories = await retrieve_relevant_memories(
        db,
        user_id,
        "favorite characters shows cartoons",
        limit=20,
    )

    found = set()

    for mem in memories:
        text = mem.content.lower()

        for c in CHARACTER_HINTS:
            if c in text:
                found.add(c)

    return list(found)
