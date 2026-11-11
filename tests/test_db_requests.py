from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import (
    CircleStatus,
    ParticipantStatus,
    RejectedBy,
    RejectionReason,
)
from app.db.requests import (
    Statistics,
    approve_circle,
    count_pending_circles,
    create_circle,
    create_mailing,
    create_user,
    finish_mailing,
    get_circle,
    get_next_pending_circle,
    get_setting,
    get_statistics,
    get_user,
    increment_auto_attempts,
    increment_resubmissions,
    mark_user_registered,
    reject_circle,
    set_circle_status,
    set_greeting_received,
    set_setting,
    set_user_banned,
    set_user_circle,
    set_user_institute,
    set_user_status,
    set_user_timezone,
    update_user_identity,
)

pytestmark = pytest.mark.asyncio


class FakeMailingSession:
    def __init__(self) -> None:
        self.added = []
        self.flush_count = 0

    def add(self, instance) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


async def test_get_user_returns_none_for_unknown_hid(session: AsyncSession) -> None:
    assert await get_user(session, "missing") is None


async def test_create_user_applies_defaults(session: AsyncSession) -> None:
    user = await create_user(session, hid="hid-1", full_name="Ivan Ivanov")

    assert user.hid == "hid-1"
    assert user.full_name == "Ivan Ivanov"
    assert user.username == "0"
    assert user.is_banned is False
    assert user.auto_attempts_used == 0
    assert user.resubmissions_used == 0
    assert user.greeting_received is False
    assert await get_user(session, "hid-1") is user


async def test_update_user_identity(session: AsyncSession) -> None:
    user = await create_user(session, hid="hid-1", full_name="Old")

    updated = await update_user_identity(
        session,
        user,
        full_name="New Name",
        username="new_user",
    )

    assert updated.full_name == "New Name"
    assert updated.username == "new_user"


async def test_user_profile_setters(session: AsyncSession) -> None:
    user = await create_user(session, hid="hid-1", full_name="Ivan")

    await set_user_status(session, user, ParticipantStatus.URFU_STUDENT)
    await set_user_institute(session, user, "ИРИТ-РТФ")
    await set_user_timezone(session, user, 5)
    await mark_user_registered(session, user, datetime(2026, 11, 11, tzinfo=UTC))
    await set_user_circle(session, user, 42)
    await set_user_banned(session, user)
    await set_greeting_received(session, user)

    assert user.status == ParticipantStatus.URFU_STUDENT
    assert user.institute == "ИРИТ-РТФ"
    assert user.timezone == 5
    assert user.registered_at == datetime(2026, 11, 11, tzinfo=UTC)
    assert user.cir_id == 42
    assert user.is_banned is True
    assert user.greeting_received is True


async def test_mark_user_registered_defaults_to_now(session: AsyncSession) -> None:
    user = await create_user(session, hid="hid-1", full_name="Ivan")

    await mark_user_registered(session, user)

    assert user.registered_at is not None
    assert user.registered_at.tzinfo is UTC


async def test_get_circle_returns_none_for_unknown_id(session: AsyncSession) -> None:
    assert await get_circle(session, 999) is None
    assert await get_next_pending_circle(session) is None
    assert await count_pending_circles(session) == 0


async def test_create_circle_uses_pending_status(session: AsyncSession) -> None:
    await create_user(session, hid="hid-1", full_name="Ivan")

    circle = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="file-id",
        duration=10,
    )

    assert circle.id > 0
    assert circle.owner_hid == "hid-1"
    assert circle.file_id == "file-id"
    assert circle.duration == 10
    assert circle.status == CircleStatus.PENDING_AUTO
    assert circle.sent_at.tzinfo is UTC
    assert await get_circle(session, circle.id) is circle


async def test_approve_and_reject_circle(session: AsyncSession) -> None:
    await create_user(session, hid="hid-1", full_name="Ivan")
    circle = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="file-id",
        duration=10,
    )

    await reject_circle(
        session,
        circle,
        reason=RejectionReason.PROFANITY,
        rejected_by=RejectedBy.AUTO,
    )

    assert circle.status == CircleStatus.REJECTED
    assert circle.rejection_reason == RejectionReason.PROFANITY
    assert circle.rejected_by == RejectedBy.AUTO

    await approve_circle(session, circle, is_buffered=True)

    assert circle.status == CircleStatus.APPROVED
    assert circle.rejection_reason is None
    assert circle.rejected_by is None
    assert circle.is_buffered is True

    await set_circle_status(session, circle, CircleStatus.APPROVED)

    assert circle.is_buffered is False


async def test_pending_queue_is_first_in_first_out(session: AsyncSession) -> None:
    await create_user(session, hid="hid-1", full_name="Ivan")
    base = datetime(2026, 11, 11, 10, tzinfo=UTC)

    later = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="later",
        duration=10,
        sent_at=base + timedelta(minutes=1),
    )
    earlier = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="earlier",
        duration=10,
        sent_at=base,
    )
    await approve_circle(session, earlier)

    assert await count_pending_circles(session) == 1
    assert await get_next_pending_circle(session) is later


async def test_counters_increment_and_return_new_values(
    session: AsyncSession,
) -> None:
    user = await create_user(session, hid="hid-1", full_name="Ivan")

    assert await increment_auto_attempts(session, user) == 1
    assert await increment_auto_attempts(session, user) == 2
    assert await increment_resubmissions(session, user) == 1
    assert user.auto_attempts_used == 2
    assert user.resubmissions_used == 1


async def test_settings_can_be_read_created_and_updated(
    session: AsyncSession,
) -> None:
    assert await get_setting(session, "intake_closed_manual") is None

    await set_setting(session, "intake_closed_manual", "true")
    assert await get_setting(session, "intake_closed_manual") == "true"

    await set_setting(session, "intake_closed_manual", "false")
    assert await get_setting(session, "intake_closed_manual") == "false"


async def test_create_mailing_adds_a_run() -> None:
    session = FakeMailingSession()
    started_at = datetime(2026, 11, 11, 10, tzinfo=UTC)

    mailing = await create_mailing(session, started_at=started_at)

    assert mailing.started_at == started_at
    assert mailing.received_hids == []
    assert session.added == [mailing]
    assert session.flush_count == 1


async def test_finish_mailing_saves_results() -> None:
    session = FakeMailingSession()
    mailing = await create_mailing(session, started_at=datetime(2026, 11, 11, tzinfo=UTC))
    finished_at = datetime(2026, 11, 11, 11, tzinfo=UTC)

    await finish_mailing(
        session,
        mailing,
        sent_count=10,
        received_count=8,
        received_hids=("hid-1", "hid-2"),
        finished_at=finished_at,
    )

    assert mailing.finished_at == finished_at
    assert mailing.sent_count == 10
    assert mailing.received_count == 8
    assert mailing.received_hids == ["hid-1", "hid-2"]
    assert session.flush_count == 2


async def test_statistics_use_yekaterinburg_day_and_spec_filters(
    session: AsyncSession,
) -> None:
    registered = await create_user(session, hid="hid-1", full_name="Registered")
    await set_user_status(session, registered, ParticipantStatus.OTHER)
    await set_user_timezone(session, registered, 3)
    await mark_user_registered(session, registered)

    consent_only = await create_user(session, hid="hid-2", full_name="Consent only")
    await mark_user_registered(session, consent_only)

    await create_user(session, hid="hid-3", full_name="Started only")

    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    day_start = datetime(2026, 11, 10, 19, tzinfo=UTC)
    day_end = datetime(2026, 11, 11, 19, tzinfo=UTC)

    before = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="before",
        duration=10,
        sent_at=day_start - timedelta(seconds=1),
    )
    first = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="first",
        duration=10,
        sent_at=day_start,
    )
    last = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="last",
        duration=10,
        sent_at=day_end - timedelta(seconds=1),
    )
    after = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="after",
        duration=10,
        sent_at=day_end,
    )

    await approve_circle(session, first)
    await approve_circle(session, last, is_buffered=True)
    await reject_circle(
        session,
        before,
        reason=RejectionReason.OTHER,
        rejected_by=RejectedBy.MANUAL,
    )
    await reject_circle(
        session,
        after,
        reason=RejectionReason.ADVERTISING,
        rejected_by=RejectedBy.AUTO,
    )

    stats = await get_statistics(session, now=now)

    assert isinstance(stats, Statistics)
    assert stats.total_users == 3
    assert stats.registered_users == 1
    assert stats.circles_total == 4
    assert stats.circles_today == 2
    assert stats.approved == 2
    assert stats.rejected_manual == 1
    assert stats.rejected_auto == 1
