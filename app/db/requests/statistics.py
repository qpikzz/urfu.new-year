"""Aggregate queries for the /stats command (FLOWS 11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.enums import CircleStatus, RejectedBy
from app.db.models import Circle, User

YEKATERINBURG = timezone(timedelta(hours=5), name="UTC+05:00")


@dataclass(frozen=True, slots=True)
class Statistics:
    total_users: int
    registered_users: int
    circles_total: int
    circles_today: int
    approved: int
    rejected_manual: int
    rejected_auto: int


def _yekaterinburg_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    local_start = now.astimezone(YEKATERINBURG).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


async def _count(session: AsyncSession, query) -> int:
    return int((await session.scalar(query)) or 0)


async def get_statistics(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> Statistics:
    day_start, day_end = _yekaterinburg_day_bounds(now or utc_now())

    total_users = await _count(
        session,
        select(func.count()).select_from(User),
    )
    registered_users = await _count(
        session,
        select(func.count())
        .select_from(User)
        .where(
            User.registered_at.is_not(None),
            User.status.is_not(None),
            User.timezone.is_not(None),
        ),
    )
    circles_total = await _count(
        session,
        select(func.count()).select_from(Circle),
    )
    circles_today = await _count(
        session,
        select(func.count())
        .select_from(Circle)
        .where(
            Circle.sent_at >= day_start,
            Circle.sent_at < day_end,
        ),
    )
    approved = await _count(
        session,
        select(func.count())
        .select_from(Circle)
        .where(Circle.status == CircleStatus.APPROVED),
    )
    rejected_manual = await _count(
        session,
        select(func.count())
        .select_from(Circle)
        .where(
            Circle.status == CircleStatus.REJECTED,
            Circle.rejected_by == RejectedBy.MANUAL,
        ),
    )
    rejected_auto = await _count(
        session,
        select(func.count())
        .select_from(Circle)
        .where(
            Circle.status == CircleStatus.REJECTED,
            Circle.rejected_by == RejectedBy.AUTO,
        ),
    )

    return Statistics(
        total_users=total_users,
        registered_users=registered_users,
        circles_total=circles_total,
        circles_today=circles_today,
        approved=approved,
        rejected_manual=rejected_manual,
        rejected_auto=rejected_auto,
    )
