"""Read and write operations for circles (DATA 3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.enums import CircleStatus, RejectedBy, RejectionReason
from app.db.models import Circle


async def get_circle(session: AsyncSession, cir_id: int) -> Circle | None:
    return await session.get(Circle, cir_id)


async def create_circle(
    session: AsyncSession,
    *,
    owner_hid: str,
    file_id: str,
    duration: int,
    sent_at: datetime | None = None,
    status: CircleStatus = CircleStatus.PENDING_AUTO,
) -> Circle:
    circle = Circle(
        owner_hid=owner_hid,
        file_id=file_id,
        duration=duration,
        sent_at=sent_at or utc_now(),
        status=status,
    )
    session.add(circle)
    await session.flush()
    return circle


async def set_circle_status(
    session: AsyncSession,
    circle: Circle,
    status: CircleStatus,
    *,
    rejection_reason: RejectionReason | None = None,
    rejected_by: RejectedBy | None = None,
    is_buffered: bool = False,
) -> Circle:
    circle.status = status
    circle.is_buffered = is_buffered
    circle.rejection_reason = (
        rejection_reason if status == CircleStatus.REJECTED else None
    )
    circle.rejected_by = rejected_by if status == CircleStatus.REJECTED else None
    await session.flush()
    return circle


async def approve_circle(
    session: AsyncSession,
    circle: Circle,
    *,
    is_buffered: bool = False,
) -> Circle:
    return await set_circle_status(
        session,
        circle,
        CircleStatus.APPROVED,
        is_buffered=is_buffered,
    )


async def reject_circle(
    session: AsyncSession,
    circle: Circle,
    *,
    reason: RejectionReason,
    rejected_by: RejectedBy,
) -> Circle:
    return await set_circle_status(
        session,
        circle,
        CircleStatus.REJECTED,
        rejection_reason=reason,
        rejected_by=rejected_by,
    )


async def get_next_pending_circle(session: AsyncSession) -> Circle | None:
    query = (
        select(Circle)
        .where(Circle.status == CircleStatus.PENDING_AUTO)
        .order_by(Circle.sent_at, Circle.id)
        .limit(1)
    )
    return (await session.scalars(query)).first()


async def count_pending_circles(session: AsyncSession) -> int:
    query = (
        select(func.count())
        .select_from(Circle)
        .where(Circle.status == CircleStatus.PENDING_AUTO)
    )
    return int((await session.scalar(query)) or 0)


async def get_circles_pending_manual(session: AsyncSession) -> list[Circle]:
    query = (
        select(Circle)
        .where(Circle.status == CircleStatus.PENDING_MANUAL)
        .order_by(Circle.sent_at, Circle.id)
    )
    return list((await session.scalars(query)).all())


async def decide_manual_circle(
    session: AsyncSession,
    cir_id: int,
    *,
    approved: bool,
    reason: RejectionReason | None = None,
) -> Circle | None:
    """Apply the first manual decision to a circle awaiting review.

    The conditional update guarantees that only one administrator wins even
    when several decisions arrive concurrently.
    """
    if not approved and reason is None:
        raise ValueError("A manual rejection requires a reason")

    values = {
        "status": CircleStatus.APPROVED if approved else CircleStatus.REJECTED,
        "is_buffered": False,
        "rejection_reason": None if approved else reason,
        "rejected_by": None if approved else RejectedBy.MANUAL,
    }
    result = await session.execute(
        update(Circle)
        .where(
            Circle.id == cir_id,
            Circle.status == CircleStatus.PENDING_MANUAL,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        return None

    await session.flush()
    return await session.get(Circle, cir_id, populate_existing=True)
