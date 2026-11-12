from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content import texts
from app.db.enums import CircleStatus, ParticipantStatus
from app.db.requests import (
    create_circle,
    create_user,
    mark_user_registered,
    set_user_banned,
    set_user_circle,
    set_user_institute,
    set_user_status,
    set_user_timezone,
)
from app.handlers import menu
from app.hid import HIDError
from app.services import (
    REGISTRATION_STEP_KEY,
    RegistrationStep,
    build_menu_text,
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


def keyboard_rows(reply_markup) -> list[list[tuple[str, str]]]:
    return [
        [(button.text, button.callback_data) for button in row]
        for row in reply_markup.inline_keyboard
    ]


async def make_registered_user(
    session: AsyncSession,
    *,
    status: ParticipantStatus = ParticipantStatus.APPLICANT,
    institute: str | None = None,
    timezone: int = 5,
) -> Any:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await set_user_status(session, user, status)
    if institute is not None:
        await set_user_institute(session, user, institute)
    await set_user_timezone(session, user, timezone)
    return user


@pytest.fixture(autouse=True)
def fake_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        menu,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


@pytest.mark.asyncio
async def test_menu_shows_profile_without_circle(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    message = make_message(text="/menu")

    await menu.handle_menu(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_awaited_once_with(build_menu_text(user))


@pytest.mark.asyncio
async def test_menu_shows_latest_circle(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="file-id",
        duration=10,
        sent_at=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
        status=CircleStatus.APPROVED,
    )
    await set_user_circle(session, user, circle.id)
    message = make_message(text="/menu")

    await menu.handle_menu(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    text = message.answer.await_args.args[0]
    assert f"🆔 ID: {circle.id}" in text
    assert "📍 Статус: Одобрен" in text
    assert "⏱ Длительность: 10 с" in text


@pytest.mark.asyncio
async def test_menu_resumes_registration_at_status(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    state = FakeFSMContext()
    message = make_message(text="/menu")

    await menu.handle_menu(message, state=state, session=session)

    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == texts.STATUS_QUESTION
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.STATUS.value


@pytest.mark.asyncio
async def test_menu_resumes_registration_at_institute_with_config(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await set_user_status(session, user, ParticipantStatus.URFU_STUDENT)
    state = FakeFSMContext()
    message = make_message(text="/menu")
    config = Config(
        bot_token="123456:fake",
        institutes=("Институт 1", "Институт 2"),
    )

    await menu.handle_menu(
        message,
        state=state,
        session=session,
        config=config,
    )

    args, kwargs = message.answer.await_args
    assert args[0] == texts.INSTITUTE_QUESTION
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [("Институт 1", "institute:0")],
        [("Институт 2", "institute:1")],
    ]
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.INSTITUTE.value


@pytest.mark.asyncio
async def test_menu_resumes_registration_at_timezone(
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
    state = FakeFSMContext()
    message = make_message(text="/menu")

    await menu.handle_menu(message, state=state, session=session)

    message.answer.assert_awaited_once_with(texts.TIMEZONE_QUESTION)
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.TIMEZONE.value


@pytest.mark.asyncio
async def test_menu_ignores_banned_participant(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    await set_user_banned(session, user)
    message = make_message(text="/menu")

    await menu.handle_menu(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_menu_ignores_unknown_participant(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/menu")

    await menu.handle_menu(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_menu_aborts_when_hid_encoding_fails(
    session: AsyncSession,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_telegram_id: int) -> str:
        raise HIDError("HID is unavailable")

    monkeypatch.setattr(menu, "telegram_id_to_hid", fail)
    message = make_message(text="/menu")

    await menu.handle_menu(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_not_awaited()
