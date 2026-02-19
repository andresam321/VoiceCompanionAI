# scripts/seed_bot_profile.py
"""
Seed a development user, device, and bot profile.
Run: python scripts/seed_bot_profile.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from db.session import get_db
from models.user import User
from models.device import Device
from models.bot_profile import BotProfile, DEFAULT_TRAITS, DEFAULT_RULES, DEFAULT_MODES
from models.user_profile import UserProfile


async def seed():
    async for db in get_db():
        # Check if seed user exists
        stmt = select(User).where(User.email == "dev@companion.local")
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            print(f"Seed user already exists: {user.id}")
        else:
            user = User(name="Dev User", email="dev@companion.local")
            db.add(user)
            await db.flush()
            print(f"Created user: {user.id}")

        # Device
        stmt = select(Device).where(Device.user_id == user.id)
        result = await db.execute(stmt)
        device = result.scalar_one_or_none()
        if not device:
            device = Device(
                user_id=user.id,
                token="dev-device-token-001",
                label="dev-pi",
                hw_model="Raspberry Pi 5",
            )
            db.add(device)
            await db.flush()
            print(f"Created device: {device.id} (token: {device.token})")

        # Bot profile 
        stmt = select(BotProfile).where(BotProfile.user_id == user.id)
        result = await db.execute(stmt)
        bp = result.scalar_one_or_none()
        if not bp:
            bp = BotProfile(
                user_id=user.id,
                name="Buddy",
                voice="nova",
                traits=DEFAULT_TRAITS,
                rules=DEFAULT_RULES,
                favorite_modes=DEFAULT_MODES,
            )
            db.add(bp)
            await db.flush()
            print(f"Created bot profile: {bp.id} ({bp.name})")

        # User profile
        stmt = select(UserProfile).where(UserProfile.user_id == user.id)
        result = await db.execute(stmt)
        up = result.scalar_one_or_none()
        if not up:
            up = UserProfile(
                user_id=user.id,
                summary="A curious and creative person who loves space and dinosaurss.",
                interests={"topics": ["space", "dinosaurs", "minecraft"]},
                preferences={"response_length": "short"},
            )
            db.add(up)
            await db.flush()
            print(f"Created user profile: {up.id}")

        print("✅ Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
