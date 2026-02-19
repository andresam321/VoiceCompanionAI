# api/app/routes/bot_profile.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.dependencies import get_current_user, get_session
from api.app.schemas.bot_profile import BotProfileResponse, BotProfileUpdate
from models.bot_profile import BotProfile, DEFAULT_TRAITS, DEFAULT_RULES, DEFAULT_MODES
from models.user import User
from services.observability import log_event

router = APIRouter(tags=["bot-profile"])


async def _get_or_create_profile(db: AsyncSession, user: User) -> BotProfile:
    stmt = select(BotProfile).where(BotProfile.user_id == user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = BotProfile(
            user_id=user.id,
            name="Buddy",
            voice="nova",
            traits=DEFAULT_TRAITS,
            rules=DEFAULT_RULES,
            favorite_modes=DEFAULT_MODES,
        )
        db.add(profile)
        await db.flush()
    return profile


@router.get("/bot-profile", response_model=BotProfileResponse)
async def get_bot_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    profile = await _get_or_create_profile(db, user)
    return BotProfileResponse.model_validate(profile)


@router.patch("/bot-profile", response_model=BotProfileResponse)
async def update_bot_profile(
    body: BotProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    profile = await _get_or_create_profile(db, user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.flush()

    await log_event(db, "bot_profile_updated", "info", source="api", metadata={
        "user_id": str(user.id),
        "fields": list(update_data.keys()),
    })

    return BotProfileResponse.model_validate(profile)
