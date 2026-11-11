"""Mailing run records (DATA 4)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models import Mailing


async def create_mailing(
    session: AsyncSession,
    *,
    started_at: datetime | None = None,
) -> Mailing:
    mailing = Mailing(
        started_at=started_at or utc_now(),
        received_hids=[],
    )
    session.add(mailing)
    await session.flush()
    return mailing


async def finish_mailing(
    session: AsyncSession,
    mailing: Mailing,
    *,
    sent_count: int,
    received_count: int,
    received_hids: Iterable[str],
    finished_at: datetime | None = None,
) -> Mailing:
    mailing.finished_at = finished_at or utc_now()
    mailing.sent_count = sent_count
    mailing.received_count = received_count
    mailing.received_hids = list(received_hids)

    await session.flush()
    return mailing
