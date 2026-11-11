"""Read and write operations for participants (DATA 2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.enums import ParticipantStatus
from app.db.models import User


async def _flush(session: AsyncSession, user: User) -> User:
    await session.flush()
    return user


async def get_user(session: AsyncSession, hid: str) -> User | None:
    return await session.get(User, hid)


async def create_user(
    session: AsyncSession,
    *,
    hid: str,
    full_name: str,
    username: str = "0",
) -> User:
    user = User(hid=hid, full_name=full_name, username=username)
    session.add(user)
    return await _flush(session, user)


async def update_user_identity(
    session: AsyncSession,
    user: User,
    *,
    full_name: str,
    username: str,
) -> User:
    user.full_name = full_name
    user.username = username
    return await _flush(session, user)


async def set_user_status(
    session: AsyncSession,
    user: User,
    status: ParticipantStatus,
) -> User:
    user.status = status
    return await _flush(session, user)


async def set_user_institute(
    session: AsyncSession,
    user: User,
    institute: str | None,
) -> User:
    user.institute = institute
    return await _flush(session, user)


async def set_user_timezone(
    session: AsyncSession,
    user: User,
    timezone: int,
) -> User:
    user.timezone = timezone
    return await _flush(session, user)


async def mark_user_registered(
    session: AsyncSession,
    user: User,
    registered_at: datetime | None = None,
) -> User:
    user.registered_at = registered_at or utc_now()
    return await _flush(session, user)


async def set_user_circle(
    session: AsyncSession,
    user: User,
    cir_id: int | None,
) -> User:
    user.cir_id = cir_id
    return await _flush(session, user)


async def set_user_banned(
    session: AsyncSession,
    user: User,
    is_banned: bool = True,
) -> User:
    user.is_banned = is_banned
    return await _flush(session, user)


async def set_greeting_received(
    session: AsyncSession,
    user: User,
    received: bool = True,
) -> User:
    user.greeting_received = received
    return await _flush(session, user)
