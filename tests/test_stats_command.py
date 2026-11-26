from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import texts
from app.db.enums import (
    ParticipantStatus,
    RejectedBy,
    RejectionReason,
)
from app.db.requests import (
    approve_circle,
    create_circle,
    create_user,
    mark_user_registered,
    reject_circle,
    set_user_status,
    set_user_timezone,
)
from app.db.requests import statistics as statistics_requests
from app.handlers import stats

NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)
DAY_START = datetime(2026, 11, 10, 19, tzinfo=UTC)
DAY_END = datetime(2026, 11, 11, 19, tzinfo=UTC)


async def make_registered_user(session: AsyncSession) -> None:
    user = await create_user(session, hid="hid-1", full_name="Registered")
    await set_user_status(session, user, ParticipantStatus.OTHER)
    await set_user_timezone(session, user, 3)
    await mark_user_registered(session, user)


@pytest.mark.asyncio
async def test_stats_command_reports_all_counters(
    session: AsyncSession,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(statistics_requests, "utc_now", lambda: NOW)
    await make_registered_user(session)
    await create_user(session, hid="hid-2", full_name="Started only")

    before = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="before",
        duration=10,
        sent_at=DAY_START - timedelta(seconds=1),
    )
    approved = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="approved",
        duration=10,
        sent_at=DAY_START,
    )
    buffered = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="buffered",
        duration=10,
        sent_at=DAY_END - timedelta(seconds=1),
    )
    auto_rejected = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="auto-rejected",
        duration=10,
        sent_at=DAY_END - timedelta(seconds=1),
    )

    await approve_circle(session, approved)
    await approve_circle(session, buffered, is_buffered=True)
    await reject_circle(
        session,
        before,
        reason=RejectionReason.OTHER,
        rejected_by=RejectedBy.MANUAL,
    )
    await reject_circle(
        session,
        auto_rejected,
        reason=RejectionReason.ADVERTISING,
        rejected_by=RejectedBy.AUTO,
    )

    message = make_message(text="/stats")
    await stats.handle_stats(message, session=session)

    message.answer.assert_awaited_once_with(
        texts.format_stats(
            total_users=2,
            registered=1,
            circles_total=4,
            circles_today=3,
            approved=1,
            rejected_manual=1,
            rejected_auto=1,
        )
    )


@pytest.mark.asyncio
async def test_stats_command_reports_zeros_on_empty_database(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/stats")

    await stats.handle_stats(message, session=session)

    message.answer.assert_awaited_once_with(
        texts.format_stats(
            total_users=0,
            registered=0,
            circles_total=0,
            circles_today=0,
            approved=0,
            rejected_manual=0,
            rejected_auto=0,
        )
    )
