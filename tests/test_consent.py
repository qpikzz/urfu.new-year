from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content import texts
from app.db.requests import (
    create_user,
    get_user,
    mark_user_registered,
    set_user_banned,
)
from app.handlers import start
from app.keyboards import (
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_CONTINUE_CALLBACK,
)
from app.services import (
    CAPTCHA_PASSED_KEY,
    CONSENT_ACCEPTED_KEY,
    REGISTRATION_STEP_KEY,
    RegistrationStep,
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

    async def clear(self) -> None:
        self.data.clear()


def consent_state() -> dict[str, Any]:
    return {
        CAPTCHA_PASSED_KEY: True,
        REGISTRATION_STEP_KEY: RegistrationStep.CONSENT.value,
    }


def make_config(
    *,
    privacy_url: str | None = "https://privacy.example",
    terms_url: str | None = "https://terms.example",
) -> Config:
    return Config(
        bot_token="123456:fake",
        privacy_url=privacy_url,
        terms_url=terms_url,
    )


def keyboard_rows(reply_markup) -> list[list[tuple[str, str]]]:
    return [
        [(button.text, button.callback_data) for button in row]
        for row in reply_markup.inline_keyboard
    ]


@pytest.fixture(autouse=True)
def fake_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        start,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


@pytest.mark.asyncio
async def test_start_at_consent_sends_configured_links(
    session: AsyncSession,
    make_message,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    message = make_message(text="/start")
    config = make_config()

    await start.handle_start(
        message,
        state=FakeFSMContext(consent_state()),
        session=session,
        config=config,
    )

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert args[0] == texts.format_consent_text(
        privacy_url="https://privacy.example",
        terms_url="https://terms.example",
    )
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [(texts.CONSENT_BUTTON, CONSENT_ACCEPT_CALLBACK)]
    ]


@pytest.mark.asyncio
async def test_start_at_consent_uses_empty_links_when_missing(
    session: AsyncSession,
    make_message,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    message = make_message(text="/start")
    config = make_config(privacy_url=None, terms_url=None)

    await start.handle_start(
        message,
        state=FakeFSMContext(consent_state()),
        session=session,
        config=config,
    )

    args = message.answer.await_args.args
    assert args[0] == texts.format_consent_text(
        privacy_url="",
        terms_url="",
    )


@pytest.mark.asyncio
async def test_continue_callback_replaces_captcha_with_consent(
    session: AsyncSession,
    make_callback,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    callback = make_callback(data=CONSENT_CONTINUE_CALLBACK)
    config = make_config()

    await start.handle_consent_continue(
        callback,
        state=FakeFSMContext(consent_state()),
        session=session,
        config=config,
    )

    callback.answer.assert_awaited_once_with()
    args, kwargs = callback.message.edit_text.await_args
    assert args[0] == texts.format_consent_text(
        privacy_url="https://privacy.example",
        terms_url="https://terms.example",
    )
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [(texts.CONSENT_BUTTON, CONSENT_ACCEPT_CALLBACK)]
    ]


@pytest.mark.asyncio
async def test_continue_callback_ignored_outside_consent_step(
    session: AsyncSession,
    make_callback,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(
        {REGISTRATION_STEP_KEY: RegistrationStep.STATUS.value}
    )
    callback = make_callback(data=CONSENT_CONTINUE_CALLBACK)

    await start.handle_consent_continue(
        callback,
        state=state,
        session=session,
        config=make_config(),
    )

    callback.answer.assert_not_awaited()
    callback.message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_consent_marks_registered_and_moves_to_status(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(consent_state())
    callback = make_callback(data=CONSENT_ACCEPT_CALLBACK)

    await start.handle_consent_accept(
        callback,
        state=state,
        session=session,
    )

    assert user.registered_at is not None
    assert state.data[CONSENT_ACCEPTED_KEY] is True
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.STATUS.value
    callback.answer.assert_awaited_once_with()
    callback.message.edit_reply_markup.assert_awaited_once_with(
        reply_markup=None
    )


@pytest.mark.asyncio
async def test_accept_consent_keeps_existing_registration_date(
    session: AsyncSession,
    make_callback,
) -> None:
    registered_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(session, user, registered_at)
    callback = make_callback(data=CONSENT_ACCEPT_CALLBACK)

    await start.handle_consent_accept(
        callback,
        state=FakeFSMContext(consent_state()),
        session=session,
    )

    assert user.registered_at == registered_at


@pytest.mark.asyncio
async def test_accept_consent_ignores_banned_participant(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_banned(session, user)
    callback = make_callback(data=CONSENT_ACCEPT_CALLBACK)

    await start.handle_consent_accept(
        callback,
        state=FakeFSMContext(consent_state()),
        session=session,
    )

    assert user.registered_at is None
    callback.answer.assert_not_awaited()
    callback.message.edit_reply_markup.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_consent_ignored_outside_consent_step(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(
        {REGISTRATION_STEP_KEY: RegistrationStep.STATUS.value}
    )
    callback = make_callback(data=CONSENT_ACCEPT_CALLBACK)

    await start.handle_consent_accept(
        callback,
        state=state,
        session=session,
    )

    assert user.registered_at is None
    callback.answer.assert_not_awaited()
    callback.message.edit_reply_markup.assert_not_awaited()


@pytest.mark.asyncio
async def test_second_accept_is_ignored_after_status_step(
    session: AsyncSession,
    make_callback,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(consent_state())
    callback = make_callback(data=CONSENT_ACCEPT_CALLBACK)

    await start.handle_consent_accept(
        callback,
        state=state,
        session=session,
    )
    await start.handle_consent_accept(
        callback,
        state=state,
        session=session,
    )

    callback.answer.assert_awaited_once_with()
    callback.message.edit_reply_markup.assert_awaited_once_with(
        reply_markup=None
    )


@pytest.mark.asyncio
async def test_consent_accept_persists_for_resume(
    session: AsyncSession,
    make_callback,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(consent_state())
    callback = make_callback(data=CONSENT_ACCEPT_CALLBACK)

    await start.handle_consent_accept(
        callback,
        state=state,
        session=session,
    )

    user = await get_user(session, "hid-1001")
    assert user is not None
    assert user.registered_at is not None
