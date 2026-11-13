from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiogram.dispatcher.event.bases import SkipHandler
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import texts
from app.db.enums import CircleStatus, ParticipantStatus
from app.db.models import Circle
from app.db.requests import (
    create_circle,
    create_user,
    get_circle,
    mark_user_registered,
    set_user_banned,
    set_user_circle,
    set_user_status,
    set_user_timezone,
)
from app.handlers import circle
from app.hid import HIDError
from app.services import (
    MAX_CIRCLE_DURATION,
    MIN_CIRCLE_DURATION,
    is_circle_in_progress,
    is_valid_circle_duration,
)


async def make_registered_user(
    session: AsyncSession,
    *,
    hid: str = "hid-1001",
) -> Any:
    user = await create_user(session, hid=hid, full_name="Test User")
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    await set_user_timezone(session, user, 5)
    return user


def make_video_note_message(
    make_message,
    *,
    duration: int | None = 10,
    file_id: str = "file-id",
) -> MagicMock:
    message = make_message()
    video_note = MagicMock()
    video_note.duration = duration
    video_note.file_id = file_id
    message.video_note = video_note
    return message


async def count_circles(session: AsyncSession) -> int:
    query = select(func.count()).select_from(Circle)
    return int((await session.scalar(query)) or 0)


@pytest.fixture(autouse=True)
def fake_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        circle,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


@pytest.mark.parametrize("duration", [MIN_CIRCLE_DURATION, MAX_CIRCLE_DURATION])
def test_duration_boundaries_are_valid(duration: int) -> None:
    assert is_valid_circle_duration(duration)


@pytest.mark.parametrize("duration", [None, -1, 0, 2, 31, 60])
def test_duration_outside_range_is_invalid(duration: int | None) -> None:
    assert not is_valid_circle_duration(duration)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (CircleStatus.PENDING_AUTO, True),
        (CircleStatus.PENDING_MANUAL, True),
        (CircleStatus.APPROVED, False),
        (CircleStatus.REJECTED, False),
    ],
)
def test_only_pending_circles_are_in_progress(
    status: CircleStatus,
    expected: bool,
) -> None:
    circle_model = Circle(
        id=1,
        owner_hid="hid-1001",
        file_id="file-id",
        duration=10,
        status=status,
    )

    assert is_circle_in_progress(circle_model) is expected


def test_no_circle_is_not_in_progress() -> None:
    assert not is_circle_in_progress(None)


@pytest.mark.asyncio
async def test_first_video_note_creates_circle_and_updates_user(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    message = make_video_note_message(
        make_message,
        duration=10,
        file_id="video-file-id",
    )

    await circle.handle_video_note(message, session=session)

    message.answer.assert_awaited_once_with(texts.CIRCLE_QUEUED)
    assert user.cir_id is not None
    stored = await get_circle(session, user.cir_id)
    assert stored is not None
    assert stored.owner_hid == user.hid
    assert stored.file_id == "video-file-id"
    assert stored.duration == 10
    assert stored.status == CircleStatus.PENDING_AUTO
    assert stored.sent_at is not None
    assert await count_circles(session) == 1


@pytest.mark.parametrize("duration", [MIN_CIRCLE_DURATION, MAX_CIRCLE_DURATION])
@pytest.mark.asyncio
async def test_valid_duration_boundaries_are_accepted(
    session: AsyncSession,
    make_message,
    duration: int,
) -> None:
    await make_registered_user(session)
    message = make_video_note_message(make_message, duration=duration)

    await circle.handle_video_note(message, session=session)

    message.answer.assert_awaited_once_with(texts.CIRCLE_QUEUED)
    assert await count_circles(session) == 1


@pytest.mark.parametrize("duration", [None, 0, 2, 31])
@pytest.mark.asyncio
async def test_invalid_duration_is_rejected_without_circle(
    session: AsyncSession,
    make_message,
    duration: int | None,
) -> None:
    user = await make_registered_user(session)
    message = make_video_note_message(make_message, duration=duration)

    await circle.handle_video_note(message, session=session)

    message.answer.assert_awaited_once_with(texts.CIRCLE_DURATION_INVALID)
    assert user.cir_id is None
    assert await count_circles(session) == 0


@pytest.mark.parametrize(
    "status",
    [CircleStatus.PENDING_AUTO, CircleStatus.PENDING_MANUAL],
)
@pytest.mark.asyncio
async def test_new_video_note_is_blocked_while_previous_is_processing(
    session: AsyncSession,
    make_message,
    status: CircleStatus,
) -> None:
    user = await make_registered_user(session)
    existing = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="existing",
        duration=10,
        status=status,
    )
    await set_user_circle(session, user, existing.id)
    message = make_video_note_message(make_message)

    await circle.handle_video_note(message, session=session)

    message.answer.assert_awaited_once_with(texts.CIRCLE_IN_PROGRESS)
    assert user.cir_id == existing.id
    assert await count_circles(session) == 1


@pytest.mark.parametrize(
    "status",
    [CircleStatus.APPROVED, CircleStatus.REJECTED],
)
@pytest.mark.asyncio
async def test_new_video_note_after_finished_circle_requires_new_command(
    session: AsyncSession,
    make_message,
    status: CircleStatus,
) -> None:
    user = await make_registered_user(session)
    existing = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="existing",
        duration=10,
        status=status,
    )
    await set_user_circle(session, user, existing.id)
    message = make_video_note_message(make_message)

    await circle.handle_video_note(message, session=session)

    message.answer.assert_awaited_once_with(texts.NEW_ASK)
    assert user.cir_id == existing.id
    assert await count_circles(session) == 1


@pytest.mark.asyncio
async def test_other_content_gets_wrong_type_reply(
    session: AsyncSession,
    make_message,
) -> None:
    await make_registered_user(session)
    message = make_message(text="привет")

    await circle.handle_other_content(message, session=session)

    message.answer.assert_awaited_once_with(texts.CIRCLE_WRONG_TYPE)


@pytest.mark.asyncio
async def test_other_content_is_ignored_while_circle_is_processing(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    existing = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="existing",
        duration=10,
        status=CircleStatus.PENDING_AUTO,
    )
    await set_user_circle(session, user, existing.id)
    message = make_message(text="привет")

    await circle.handle_other_content(message, session=session)

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_content_skips_incomplete_registration(
    session: AsyncSession,
    make_message,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    message = make_message(text="5")

    with pytest.raises(SkipHandler):
        await circle.handle_other_content(message, session=session)

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_command_skips_to_command_router(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/menu")

    with pytest.raises(SkipHandler):
        await circle.handle_other_content(message, session=session)

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_video_note_ignored_for_incomplete_registration(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    message = make_video_note_message(make_message)

    await circle.handle_video_note(message, session=session)

    message.answer.assert_not_awaited()
    assert user.cir_id is None
    assert await count_circles(session) == 0


@pytest.mark.asyncio
async def test_banned_participant_is_ignored(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    await set_user_banned(session, user)
    message = make_video_note_message(make_message)

    await circle.handle_video_note(message, session=session)

    message.answer.assert_not_awaited()
    assert await count_circles(session) == 0


@pytest.mark.asyncio
async def test_video_note_aborts_when_hid_encoding_fails(
    session: AsyncSession,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_telegram_id: int) -> str:
        raise HIDError("HID is unavailable")

    monkeypatch.setattr(circle, "telegram_id_to_hid", fail)
    message = make_video_note_message(make_message)

    await circle.handle_video_note(message, session=session)

    message.answer.assert_not_awaited()
    assert await count_circles(session) == 0
