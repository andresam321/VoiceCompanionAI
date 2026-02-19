# api/app/dependencies.py
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.device import Device
from models.user import User


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


async def get_current_device(
    x_device_token: str = Header(..., alias="X-Device-Token"),
    db: AsyncSession = Depends(get_session),
) -> Device:
    """Authenticate a device by its token header."""
    stmt = select(Device).where(Device.token == x_device_token)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device token",
        )
    return device


async def get_current_user(
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the user from the authenticated device."""
    user = await db.get(User, device.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
