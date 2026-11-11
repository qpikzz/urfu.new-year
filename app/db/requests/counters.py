"""Per-participant moderation counters (DATA 2, FLOWS 7)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def increment_auto_attempts(session: AsyncSession, user: User) -> int:
    user.auto_attempts_used += 1
    await session.flush()
    return user.auto_attempts_used


async def increment_resubmissions(session: AsyncSession, user: User) -> int:
    user.resubmissions_used += 1
    await session.flush()
    return user.resubmissions_used
