from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.config import Config
from app.hid import HIDError
from app.middlewares import AdminAccessMiddleware
from app.services.admin_access import (
    admin_command_from_text,
    is_admin_command,
    is_admin_hid,
    resolve_admin_hid,
)

ADMIN_TELEGRAM_ID = 1001
ADMIN_HID = f"hid-{ADMIN_TELEGRAM_ID}"


def make_config(admin_hids: tuple[str, ...] = (ADMIN_HID,)) -> Config:
    return Config(bot_token="123456:fake", admin_hids=admin_hids)


@pytest.fixture(autouse=True)
def fake_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.admin_access.telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


@pytest.mark.parametrize(
    ("hid", "config", "expected"),
    [
        (ADMIN_HID, make_config(), True),
        ("hid-9999", make_config(), False),
        (None, make_config(), False),
        (ADMIN_HID, None, False),
        ("", make_config(), False),
    ],
)
def test_is_admin_hid(
    hid: str | None,
    config: Config | None,
    expected: bool,
) -> None:
    assert is_admin_hid(hid, config) is expected


def test_resolve_admin_hid_returns_admin(telegram_user) -> None:
    assert resolve_admin_hid(telegram_user, make_config()) == ADMIN_HID


def test_resolve_admin_hid_rejects_non_admin(telegram_user) -> None:
    config = make_config(admin_hids=("hid-9999",))

    assert resolve_admin_hid(telegram_user, config) is None


def test_resolve_admin_hid_handles_missing_user() -> None:
    assert resolve_admin_hid(None, make_config()) is None


def test_resolve_admin_hid_handles_missing_config(telegram_user) -> None:
    assert resolve_admin_hid(telegram_user, None) is None


def test_resolve_admin_hid_handles_hid_error(
    telegram_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_telegram_id: int) -> str:
        raise HIDError("HID is unavailable")

    monkeypatch.setattr("app.services.admin_access.telegram_id_to_hid", fail)

    assert resolve_admin_hid(telegram_user, make_config()) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/look", "look"),
        ("/look 42", "look"),
        ("/look@urfu_bot 42", "look"),
        (" /close", "close"),
        ("/BAN hid-1", "ban"),
        ("/start", None),
        ("/looks", None),
        ("look", None),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_admin_command_from_text(
    text: str | None,
    expected: str | None,
) -> None:
    assert admin_command_from_text(text) == expected


def test_is_admin_command() -> None:
    assert is_admin_command("/stats") is True
    assert is_admin_command("/menu") is False


@pytest.mark.asyncio
async def test_non_admin_admin_command_is_ignored(make_message) -> None:
    message = make_message(text="/look 42")
    handler = AsyncMock()
    middleware = AdminAccessMiddleware()
    config = make_config(admin_hids=("hid-9999",))

    result = await middleware(
        handler,
        message,
        {"event_from_user": message.from_user, "config": config},
    )

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_command_reaches_handler(make_message) -> None:
    message = make_message(text="/look@urfu_bot 42")
    handler = AsyncMock(return_value="handled")
    middleware = AdminAccessMiddleware()
    data = {"event_from_user": message.from_user, "config": make_config()}

    result = await middleware(handler, message, data)

    assert result == "handled"
    handler.assert_awaited_once_with(message, data)


@pytest.mark.asyncio
async def test_regular_command_from_non_admin_reaches_handler(
    make_message,
) -> None:
    message = make_message(text="/menu")
    handler = AsyncMock(return_value="handled")
    middleware = AdminAccessMiddleware()
    data = {
        "event_from_user": message.from_user,
        "config": make_config(admin_hids=("hid-9999",)),
    }

    result = await middleware(handler, message, data)

    assert result == "handled"
    handler.assert_awaited_once_with(message, data)


@pytest.mark.asyncio
async def test_admin_command_without_config_is_ignored(make_message) -> None:
    message = make_message(text="/ban hid-1")
    handler = AsyncMock()
    middleware = AdminAccessMiddleware()

    result = await middleware(
        handler,
        message,
        {"event_from_user": message.from_user},
    )

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_command_without_user_is_ignored(make_message) -> None:
    message = make_message(text="/stats")
    message.from_user = None
    handler = AsyncMock()
    middleware = AdminAccessMiddleware()

    result = await middleware(handler, message, {"config": make_config()})

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_command_with_hid_error_is_ignored(
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_telegram_id: int) -> str:
        raise HIDError("HID is unavailable")

    monkeypatch.setattr("app.services.admin_access.telegram_id_to_hid", fail)
    message = make_message(text="/stats")
    handler = AsyncMock()
    middleware = AdminAccessMiddleware()

    result = await middleware(
        handler,
        message,
        {"event_from_user": message.from_user, "config": make_config()},
    )

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_message_event_reaches_handler(make_callback) -> None:
    callback = make_callback()
    handler = AsyncMock(return_value="handled")
    middleware = AdminAccessMiddleware()

    result = await middleware(
        handler,
        callback,
        {"event_from_user": callback.from_user, "config": make_config()},
    )

    assert result == "handled"
    handler.assert_awaited_once()
