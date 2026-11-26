from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content import texts
from app.db.enums import CircleStatus, ParticipantStatus
from app.db.models import Circle
from app.db.requests import (
    create_circle,
    create_user,
    get_setting,
    mark_user_registered,
    set_user_circle,
    set_user_status,
    set_user_timezone,
)
from app.handlers import circle, close, new, start
from app.services import (
    AWAITING_NEW_CIRCLE_KEY,
    MANUAL_CLOSE_SETTING_KEY,
    REGISTRATION_STEP_KEY,
    IntakeClosure,
    IntakeReason,
    RegistrationStep,
    active_closures,
    apply_automatic_closure,
    automatic_closures,
    intake_closed_message,
    is_intake_closed,
    is_manual_closed,
    notify_environment_closure,
    remove_automatic_closure,
    reset_automatic_closures,
    toggle_manual_closure,
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


def make_config(
    *,
    intake_closed: bool = False,
    admin_chat_id: int | None = -100,
    channel_url: str = "https://channel",
) -> Config:
    return Config(
        bot_token="123456:fake",
        admin_chat_id=admin_chat_id,
        channel_url=channel_url,
        intake_closed=intake_closed,
    )


@pytest.fixture(autouse=True)
def reset_intake_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    reset_automatic_closures()
    monkeypatch.setattr(
        circle,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )
    monkeypatch.setattr(
        new,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )
    monkeypatch.setattr(
        start,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )
    yield
    reset_automatic_closures()


async def make_registered_user(
    session: AsyncSession,
    *,
    hid: str = "hid-1001",
    timezone: int | None = 5,
) -> Any:
    user = await create_user(session, hid=hid, full_name="Test User")
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    if timezone is not None:
        await set_user_timezone(session, user, timezone)
    return user


def make_video_note_message(
    make_message,
    *,
    duration: int | None = 10,
) -> MagicMock:
    message = make_message()
    video_note = MagicMock()
    video_note.duration = duration
    video_note.file_id = "file-id"
    message.video_note = video_note
    return message


async def count_circles(session: AsyncSession) -> int:
    query = select(func.count()).select_from(Circle)
    return int((await session.scalar(query)) or 0)


@pytest.mark.asyncio
async def test_manual_toggle_persists_and_closes_intake(
    session: AsyncSession,
) -> None:
    config = make_config()

    assert not await is_intake_closed(session, config)
    assert await toggle_manual_closure(session, config=config) is True
    assert await get_setting(session, MANUAL_CLOSE_SETTING_KEY) == "true"
    assert await is_manual_closed(session)
    assert await is_intake_closed(session, config)

    assert await toggle_manual_closure(session, config=config) is False
    assert await get_setting(session, MANUAL_CLOSE_SETTING_KEY) == "false"
    assert not await is_manual_closed(session)
    assert not await is_intake_closed(session, config)


@pytest.mark.asyncio
async def test_environment_flag_closes_intake(session: AsyncSession) -> None:
    config = make_config(intake_closed=True)

    assert await is_intake_closed(session, config)
    closures = await active_closures(session, config)
    assert [closure.reason for closure in closures] == [
        IntakeReason.ENVIRONMENT
    ]


@pytest.mark.asyncio
async def test_automatic_closure_closes_and_reopens_intake(
    session: AsyncSession,
    bot,
) -> None:
    config = make_config()
    closure = IntakeClosure(
        IntakeReason.CPU,
        texts.format_intake_reason_cpu(95),
    )

    assert await apply_automatic_closure(
        session,
        bot,
        config,
        closure,
    )
    assert await is_intake_closed(session, config)
    assert automatic_closures() == (closure,)
    bot.send_message.assert_awaited_once()
    assert texts.TEXTS["intake.reason.cpu"].split("{")[0] in (
        bot.send_message.await_args.kwargs["text"]
    )

    assert await remove_automatic_closure(
        session,
        bot,
        config,
        IntakeReason.CPU,
    )
    assert not await is_intake_closed(session, config)
    assert automatic_closures() == ()
    assert bot.send_message.await_count == 2
    assert "Приём кружков открыт" in (
        bot.send_message.await_args.kwargs["text"]
    )


@pytest.mark.asyncio
async def test_notifications_only_on_state_transitions(
    session: AsyncSession,
    bot,
) -> None:
    config = make_config()
    cpu = IntakeClosure(
        IntakeReason.CPU,
        texts.format_intake_reason_cpu(95),
    )
    disk = IntakeClosure(
        IntakeReason.DISK,
        texts.format_intake_reason_disk(0.5),
    )

    assert await apply_automatic_closure(session, bot, config, cpu)
    assert not await apply_automatic_closure(session, bot, config, disk)
    assert bot.send_message.await_count == 1

    assert not await remove_automatic_closure(
        session,
        bot,
        config,
        IntakeReason.CPU,
    )
    assert bot.send_message.await_count == 1
    assert await is_intake_closed(session, config)

    assert await remove_automatic_closure(
        session,
        bot,
        config,
        IntakeReason.DISK,
    )
    assert bot.send_message.await_count == 2
    assert not await is_intake_closed(session, config)


@pytest.mark.asyncio
async def test_manual_toggle_notifies_only_on_transitions(
    session: AsyncSession,
    bot,
) -> None:
    config = make_config()

    assert await toggle_manual_closure(
        session,
        bot=bot,
        config=config,
    )
    assert bot.send_message.await_count == 1
    assert "Приём кружков закрыт" in (
        bot.send_message.await_args.kwargs["text"]
    )
    assert texts.TEXTS["intake.reason.manual"] in (
        bot.send_message.await_args.kwargs["text"]
    )

    assert not await toggle_manual_closure(
        session,
        bot=bot,
        config=config,
    )
    assert bot.send_message.await_count == 2
    assert "Приём кружков открыт" in (
        bot.send_message.await_args.kwargs["text"]
    )


@pytest.mark.asyncio
async def test_manual_toggle_keeps_silent_when_environment_still_closes(
    session: AsyncSession,
    bot,
) -> None:
    config = make_config(intake_closed=True)

    assert await toggle_manual_closure(
        session,
        bot=bot,
        config=config,
    )
    assert not await toggle_manual_closure(
        session,
        bot=bot,
        config=config,
    )

    bot.send_message.assert_not_awaited()
    assert await is_intake_closed(session, config)


@pytest.mark.asyncio
async def test_notification_is_skipped_without_admin_chat(
    session: AsyncSession,
    bot,
) -> None:
    config = make_config(admin_chat_id=None)
    closure = IntakeClosure(
        IntakeReason.QUEUE,
        texts.format_intake_reason_queue(1200),
    )

    assert await apply_automatic_closure(
        session,
        bot,
        config,
        closure,
    )
    bot.send_message.assert_not_awaited()
    assert await is_intake_closed(session, config)


@pytest.mark.asyncio
async def test_environment_closure_notification(
    bot,
) -> None:
    config = make_config(intake_closed=True)

    assert await notify_environment_closure(bot, config)
    bot.send_message.assert_awaited_once()
    assert texts.TEXTS["intake.reason.environment"] in (
        bot.send_message.await_args.kwargs["text"]
    )

    bot.send_message.reset_mock()
    assert not await notify_environment_closure(
        bot,
        make_config(intake_closed=False),
    )
    bot.send_message.assert_not_awaited()


def test_intake_closed_message_uses_channel_url() -> None:
    config = make_config(channel_url="https://t.me/channel")

    assert intake_closed_message(config) == texts.format_intake_closed(
        channel_url="https://t.me/channel",
    )
    assert intake_closed_message(None) == texts.format_intake_closed(
        channel_url="",
    )


@pytest.mark.asyncio
async def test_close_handler_toggles_manual_closure(
    session: AsyncSession,
    make_message,
    bot,
) -> None:
    config = make_config()
    message = make_message(text="/close")

    await close.handle_close(
        message,
        session=session,
        bot=bot,
        config=config,
    )

    message.answer.assert_awaited_once_with(texts.CLOSE_ON)
    assert await is_manual_closed(session)
    assert bot.send_message.await_count == 1

    message = make_message(text="/close")
    await close.handle_close(
        message,
        session=session,
        bot=bot,
        config=config,
    )

    message.answer.assert_awaited_once_with(texts.CLOSE_OFF)
    assert not await is_manual_closed(session)
    assert bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_close_handler_when_environment_flag_is_active(
    session: AsyncSession,
    make_message,
    bot,
) -> None:
    config = make_config(intake_closed=True)

    message = make_message(text="/close")
    await close.handle_close(
        message,
        session=session,
        bot=bot,
        config=config,
    )
    message.answer.assert_awaited_once_with(texts.CLOSE_ON)

    message = make_message(text="/close")
    await close.handle_close(
        message,
        session=session,
        bot=bot,
        config=config,
    )
    message.answer.assert_awaited_once_with(texts.CLOSE_OFF)

    bot.send_message.assert_not_awaited()
    assert await is_intake_closed(session, config)


@pytest.mark.asyncio
async def test_video_note_is_rejected_when_intake_closed(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    config = make_config(intake_closed=True)
    state = FakeFSMContext({AWAITING_NEW_CIRCLE_KEY: True})
    message = make_video_note_message(make_message)

    await circle.handle_video_note(
        message,
        session=session,
        state=state,
        config=config,
    )

    message.answer.assert_awaited_once_with(intake_closed_message(config))
    assert user.cir_id is None
    assert await count_circles(session) == 0
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is False


@pytest.mark.asyncio
async def test_closed_intake_wins_over_invalid_duration(
    session: AsyncSession,
    make_message,
) -> None:
    await make_registered_user(session)
    config = make_config(intake_closed=True)
    message = make_video_note_message(make_message, duration=2)

    await circle.handle_video_note(
        message,
        session=session,
        config=config,
    )

    message.answer.assert_awaited_once_with(intake_closed_message(config))
    assert await count_circles(session) == 0


@pytest.mark.asyncio
async def test_closed_intake_wins_over_previous_circle_in_progress(
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
    config = make_config(intake_closed=True)
    message = make_video_note_message(make_message)

    await circle.handle_video_note(
        message,
        session=session,
        config=config,
    )

    message.answer.assert_awaited_once_with(intake_closed_message(config))
    assert await count_circles(session) == 1


@pytest.mark.asyncio
async def test_new_is_rejected_when_intake_closed(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    circle_model = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="existing",
        duration=10,
        status=CircleStatus.APPROVED,
    )
    await set_user_circle(session, user, circle_model.id)
    config = make_config(intake_closed=True)
    state = FakeFSMContext()
    message = make_message(text="/new")

    await new.handle_new(
        message,
        state=state,
        session=session,
        config=config,
    )

    message.answer.assert_awaited_once_with(intake_closed_message(config))
    assert state.data[AWAITING_NEW_CIRCLE_KEY] is False


@pytest.mark.asyncio
async def test_new_without_circle_is_rejected_when_intake_closed(
    session: AsyncSession,
    make_message,
) -> None:
    await make_registered_user(session)
    config = make_config(intake_closed=True)
    message = make_message(text="/new")

    await new.handle_new(
        message,
        state=FakeFSMContext(),
        session=session,
        config=config,
    )

    message.answer.assert_awaited_once_with(intake_closed_message(config))


@pytest.mark.asyncio
async def test_registration_completion_sends_closed_message(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session, timezone=None)
    config = make_config(intake_closed=True)
    state = FakeFSMContext(
        {REGISTRATION_STEP_KEY: RegistrationStep.TIMEZONE.value}
    )
    message = make_message(text="5")

    await start.handle_timezone_input(
        message,
        state=state,
        session=session,
        config=config,
    )

    assert message.answer.await_args_list[0].args[0] == texts.REGISTRATION_DONE
    assert message.answer.await_args_list[1].args[0] == (
        intake_closed_message(config)
    )
    assert user.timezone == 5


@pytest.mark.asyncio
async def test_registration_completion_asks_for_circle_when_open(
    session: AsyncSession,
    make_message,
) -> None:
    await make_registered_user(session, timezone=None)
    config = make_config()
    state = FakeFSMContext(
        {REGISTRATION_STEP_KEY: RegistrationStep.TIMEZONE.value}
    )
    message = make_message(text="5")

    await start.handle_timezone_input(
        message,
        state=state,
        session=session,
        config=config,
    )

    assert message.answer.await_args_list[0].args[0] == texts.REGISTRATION_DONE
    assert message.answer.await_args_list[1].args[0] == texts.CIRCLE_ASK
