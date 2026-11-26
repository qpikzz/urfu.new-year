from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.dispatcher.event.bases import SkipHandler

from app.config import Config
from app.content import texts
from app.db.models import Mailing, User
from app.handlers import send
from app.hid import HIDError
from app.services import announcement

ADMIN_TELEGRAM_ID = 1001
ADMIN_HID = f"hid-{ADMIN_TELEGRAM_ID}"


class FakeFSMContext:
    def __init__(self, state: object | None = None) -> None:
        self.state = state

    async def set_state(self, state: object) -> None:
        self.state = state

    async def clear(self) -> None:
        self.state = None


class FakeMailingSession:
    def __init__(self) -> None:
        self.added: list[Mailing] = []
        self.flush_count = 0

    def add(self, instance: Mailing) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


def make_config(admin_hids: tuple[str, ...] = (ADMIN_HID,)) -> Config:
    return Config(bot_token="123456:fake", admin_hids=admin_hids)


@pytest.fixture(autouse=True)
def fake_admin_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.admin_access.telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    sleep = AsyncMock()
    monkeypatch.setattr(
        announcement,
        "asyncio",
        SimpleNamespace(sleep=sleep),
    )
    return sleep


@pytest.mark.asyncio
async def test_send_announcement_records_attempts_and_deliveries(
    bot: AsyncMock,
    no_sleep: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeMailingSession()
    users = [
        User(hid="hid-1", full_name="First"),
        User(hid="hid-2", full_name="Second"),
        User(hid="hid-3", full_name="Third"),
    ]
    monkeypatch.setattr(
        announcement,
        "hid_to_telegram_id",
        lambda hid: int(hid.removeprefix("hid-")),
    )
    bot.copy_message = AsyncMock(
        side_effect=[None, RuntimeError("blocked"), None]
    )

    mailing = await announcement.send_announcement(
        session,
        bot,
        from_chat_id=-100,
        message_id=42,
        users=users,
    )

    assert mailing.sent_count == 3
    assert mailing.received_count == 2
    assert mailing.received_hids == ["hid-1", "hid-3"]
    assert mailing.started_at is not None
    assert mailing.finished_at is not None
    assert bot.copy_message.await_count == 3
    assert no_sleep.await_count == 2
    assert no_sleep.await_args.args == (announcement.MAILING_DELAY_SECONDS,)


@pytest.mark.asyncio
async def test_send_announcement_skips_invalid_hid_without_retry(
    bot: AsyncMock,
    no_sleep: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeMailingSession()
    users = [
        User(hid="hid-1", full_name="First"),
        User(hid="hid-bad", full_name="Broken"),
    ]

    def decode(hid: str) -> int:
        if hid == "hid-bad":
            raise HIDError("invalid HID")
        return int(hid.removeprefix("hid-"))

    monkeypatch.setattr(announcement, "hid_to_telegram_id", decode)
    bot.copy_message = AsyncMock()

    mailing = await announcement.send_announcement(
        session,
        bot,
        from_chat_id=-100,
        message_id=42,
        users=users,
    )

    assert mailing.sent_count == 2
    assert mailing.received_count == 1
    assert mailing.received_hids == ["hid-1"]
    bot.copy_message.assert_awaited_once_with(
        chat_id=1,
        from_chat_id=-100,
        message_id=42,
    )


@pytest.mark.asyncio
async def test_send_command_asks_for_message(
    make_message,
) -> None:
    state = FakeFSMContext()
    message = make_message(text="/send")

    await send.handle_send(message, state=state, config=make_config())

    message.answer.assert_awaited_once_with(texts.SEND_ASK)
    assert state.state == send.AnnouncementStates.awaiting_message


@pytest.mark.asyncio
async def test_send_command_ignores_non_admin(make_message) -> None:
    state = FakeFSMContext()
    message = make_message(text="/send")

    await send.handle_send(
        message,
        state=state,
        config=make_config(admin_hids=("hid-9999",)),
    )

    message.answer.assert_not_awaited()
    assert state.state is None


@pytest.mark.asyncio
async def test_announcement_handler_copies_message_and_reports_done(
    make_message,
    bot: AsyncMock,
    no_sleep: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeMailingSession()
    users = [
        User(hid=ADMIN_HID, full_name="Admin"),
        User(hid="hid-2002", full_name="Participant"),
    ]

    async def fake_get_all_users(_session: object) -> list[User]:
        return users

    monkeypatch.setattr(send, "get_all_users", fake_get_all_users)
    monkeypatch.setattr(
        announcement,
        "hid_to_telegram_id",
        lambda hid: int(hid.removeprefix("hid-")),
    )
    bot.copy_message = AsyncMock()

    message = make_message(text="Hello everyone")
    message.chat.id = -100
    message.message_id = 42
    state = FakeFSMContext(send.AnnouncementStates.awaiting_message)

    await send.handle_announcement(
        message,
        state=state,
        bot=bot,
        session=session,
        config=make_config(),
    )

    calls = message.answer.await_args_list
    assert calls[0].args[0] == texts.SEND_STARTED
    done_text = calls[1].args[0]
    assert "📤 Отправлено: 2" in done_text
    assert "📥 Получили: 2" in done_text
    assert "🕒 Начало: " in done_text
    assert " ЕКБ" in done_text
    assert state.state is None
    assert bot.copy_message.await_count == 2

    mailings = session.added
    assert len(mailings) == 1
    assert mailings[0].sent_count == 2
    assert mailings[0].received_count == 2
    assert mailings[0].received_hids == [ADMIN_HID, "hid-2002"]


@pytest.mark.asyncio
async def test_command_while_awaiting_is_not_broadcast(
    make_message,
    bot: AsyncMock,
) -> None:
    session = FakeMailingSession()
    message = make_message(text="/stats")
    state = FakeFSMContext(send.AnnouncementStates.awaiting_message)

    with pytest.raises(SkipHandler):
        await send.handle_announcement(
            message,
            state=state,
            bot=bot,
            session=session,
            config=make_config(),
        )

    message.answer.assert_not_awaited()
    assert state.state == send.AnnouncementStates.awaiting_message


@pytest.mark.asyncio
async def test_announcement_from_non_admin_is_ignored(
    make_message,
    bot: AsyncMock,
) -> None:
    session = FakeMailingSession()
    message = make_message(text="Hello")
    state = FakeFSMContext(send.AnnouncementStates.awaiting_message)

    await send.handle_announcement(
        message,
        state=state,
        bot=bot,
        session=session,
        config=make_config(admin_hids=("hid-9999",)),
    )

    message.answer.assert_not_awaited()
    assert state.state == send.AnnouncementStates.awaiting_message
