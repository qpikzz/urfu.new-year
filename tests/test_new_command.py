from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import texts
from app.db.enums import (
    CircleStatus,
    ParticipantStatus,
    RejectedBy,
    RejectionReason,
)
from app.db.models import Circle
from app.db.requests import (
    create_circle,
    create_user,
    get_circle,
    mark_user_registered,
    reject_circle,
    set_user_banned,
    set_user_circle,
    set_user_status,
    set_user_timezone,
)
from app.handlers import circle as circle_handler
from app.handlers import new
from app.hid import HIDError
from app.services import (
    AWAITING_NEW_CIRCLE_KEY,
    REGISTRATION_STEP_KEY,
    RegistrationStep,
    is_awaiting_new_circle,
    was_manually_rejected,
)


class FakeFSMContext:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = dict(data or {})

    async def get_data(self) -> dict[str, Any]:
        return dict(self.data)

    async def update_data(
        self,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        values = dict(data or {})
        values.update(kwargs)
        self.data.update(values)


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
    file_id: str = "new-file-id",
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
        new,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )
    monkeypatch.setattr(
        circle_handler,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


@pytest.mark.asyncio
async def test_new_continues_incomplete_registration(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    state = FakeFSMContext({AWAITING_NEW_CIRCLE_KEY: True})
    message = make_message(text="/new")

    await new.handle_new(message, state=state, session=session)

    message.answer.assert_awaited_once_with(texts.TIMEZONE_QUESTION)
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.TIMEZONE.value
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is False


@pytest.mark.asyncio
async def test_new_without_circle_replies_no_circle(
    session: AsyncSession,
    make_message,
) -> None:
    await make_registered_user(session)
    state = FakeFSMContext({AWAITING_NEW_CIRCLE_KEY: True})
    message = make_message(text="/new")

    await new.handle_new(message, state=state, session=session)

    message.answer.assert_awaited_once_with(texts.NEW_NO_CIRCLE)
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is False


@pytest.mark.parametrize(
    "status",
    [CircleStatus.PENDING_AUTO, CircleStatus.PENDING_MANUAL],
)
@pytest.mark.asyncio
async def test_new_is_unavailable_while_circle_is_processing(
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
    state = FakeFSMContext({AWAITING_NEW_CIRCLE_KEY: True})
    message = make_message(text="/new")

    await new.handle_new(message, state=state, session=session)

    message.answer.assert_awaited_once_with(texts.NEW_UNAVAILABLE)
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is False


@pytest.mark.parametrize(
    "status",
    [CircleStatus.APPROVED, CircleStatus.REJECTED],
)
@pytest.mark.asyncio
async def test_new_asks_for_circle_after_finished_status(
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
    state = FakeFSMContext()
    message = make_message(text="/new")

    await new.handle_new(message, state=state, session=session)

    message.answer.assert_awaited_once_with(texts.NEW_ASK)
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is True


@pytest.mark.asyncio
async def test_new_ignores_banned_participant(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    await set_user_banned(session, user)
    message = make_message(text="/new")

    await new.handle_new(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_ignores_unknown_participant(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/new")

    await new.handle_new(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_aborts_when_hid_encoding_fails(
    session: AsyncSession,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_telegram_id: int) -> str:
        raise HIDError("HID is unavailable")

    monkeypatch.setattr(new, "telegram_id_to_hid", fail)
    message = make_message(text="/new")

    await new.handle_new(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_then_video_note_replaces_circle(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    old_circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="old-file-id",
        duration=10,
        status=CircleStatus.APPROVED,
    )
    await set_user_circle(session, user, old_circle.id)
    state = FakeFSMContext()

    await new.handle_new(
        make_message(text="/new"),
        state=state,
        session=session,
    )
    message = make_video_note_message(
        make_message,
        file_id="new-file-id",
        duration=15,
    )
    await circle_handler.handle_video_note(
        message,
        session=session,
        state=state,
    )

    message.answer.assert_awaited_once_with(texts.CIRCLE_QUEUED)
    assert user.cir_id is not None
    assert user.cir_id != old_circle.id
    stored = await get_circle(session, user.cir_id)
    assert stored is not None
    assert stored.file_id == "new-file-id"
    assert stored.duration == 15
    assert stored.status == CircleStatus.PENDING_AUTO
    assert await get_circle(session, old_circle.id) is not None
    assert await count_circles(session) == 2
    assert user.resubmissions_used == 0
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is False


@pytest.mark.asyncio
async def test_new_after_manual_rejection_increments_resubmissions(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    old_circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="old-file-id",
        duration=10,
        status=CircleStatus.PENDING_MANUAL,
    )
    await reject_circle(
        session,
        old_circle,
        reason=RejectionReason.PROFANITY,
        rejected_by=RejectedBy.MANUAL,
    )
    await set_user_circle(session, user, old_circle.id)
    state = FakeFSMContext()

    await new.handle_new(
        make_message(text="/new"),
        state=state,
        session=session,
    )
    await circle_handler.handle_video_note(
        make_video_note_message(make_message),
        session=session,
        state=state,
    )

    assert user.resubmissions_used == 1
    assert user.cir_id != old_circle.id


@pytest.mark.asyncio
async def test_new_after_auto_rejection_does_not_increment_resubmissions(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    old_circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="old-file-id",
        duration=10,
        status=CircleStatus.PENDING_AUTO,
    )
    await reject_circle(
        session,
        old_circle,
        reason=RejectionReason.PROFANITY,
        rejected_by=RejectedBy.AUTO,
    )
    await set_user_circle(session, user, old_circle.id)
    state = FakeFSMContext()

    await new.handle_new(
        make_message(text="/new"),
        state=state,
        session=session,
    )
    await circle_handler.handle_video_note(
        make_video_note_message(make_message),
        session=session,
        state=state,
    )

    assert user.resubmissions_used == 0
    assert user.cir_id != old_circle.id


@pytest.mark.asyncio
async def test_video_note_without_new_still_requires_new_command(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    old_circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="old-file-id",
        duration=10,
        status=CircleStatus.APPROVED,
    )
    await set_user_circle(session, user, old_circle.id)
    state = FakeFSMContext()
    message = make_video_note_message(make_message)

    await circle_handler.handle_video_note(
        message,
        session=session,
        state=state,
    )

    message.answer.assert_awaited_once_with(texts.NEW_ASK)
    assert user.cir_id == old_circle.id
    assert await count_circles(session) == 1


@pytest.mark.asyncio
async def test_invalid_duration_after_new_keeps_request(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    old_circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="old-file-id",
        duration=10,
        status=CircleStatus.APPROVED,
    )
    await set_user_circle(session, user, old_circle.id)
    state = FakeFSMContext()

    await new.handle_new(
        make_message(text="/new"),
        state=state,
        session=session,
    )
    message = make_video_note_message(make_message, duration=2)
    await circle_handler.handle_video_note(
        message,
        session=session,
        state=state,
    )

    message.answer.assert_awaited_once_with(texts.CIRCLE_DURATION_INVALID)
    assert user.cir_id == old_circle.id
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is True
    assert await count_circles(session) == 1


@pytest.mark.asyncio
async def test_non_circle_after_new_keeps_request(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    old_circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="old-file-id",
        duration=10,
        status=CircleStatus.APPROVED,
    )
    await set_user_circle(session, user, old_circle.id)
    state = FakeFSMContext()

    await new.handle_new(
        make_message(text="/new"),
        state=state,
        session=session,
    )
    message = make_message(text="не кружок")
    await circle_handler.handle_other_content(message, session=session)

    message.answer.assert_awaited_once_with(texts.CIRCLE_WRONG_TYPE)
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is True


def test_manual_rejection_detection() -> None:
    manual = Circle(
        id=1,
        owner_hid="hid-1001",
        file_id="file-id",
        duration=10,
        status=CircleStatus.REJECTED,
        rejected_by=RejectedBy.MANUAL,
    )
    automatic = Circle(
        id=2,
        owner_hid="hid-1001",
        file_id="file-id",
        duration=10,
        status=CircleStatus.REJECTED,
        rejected_by=RejectedBy.AUTO,
    )
    approved = Circle(
        id=3,
        owner_hid="hid-1001",
        file_id="file-id",
        duration=10,
        status=CircleStatus.APPROVED,
    )

    assert was_manually_rejected(manual)
    assert not was_manually_rejected(automatic)
    assert not was_manually_rejected(approved)
    assert not was_manually_rejected(None)


def test_awaiting_new_circle_flag() -> None:
    assert is_awaiting_new_circle({AWAITING_NEW_CIRCLE_KEY: True})
    assert not is_awaiting_new_circle({AWAITING_NEW_CIRCLE_KEY: False})
    assert not is_awaiting_new_circle({})
    assert not is_awaiting_new_circle(None)
