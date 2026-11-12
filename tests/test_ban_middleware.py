from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.requests import create_user, set_user_banned
from app.hid import HIDError
from app.middlewares import BanMiddleware


@pytest.fixture(autouse=True)
def fake_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.middlewares.telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


@pytest.mark.asyncio
async def test_banned_message_is_ignored(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Banned User")
    await set_user_banned(session, user)
    message = make_message(text="/start")
    handler = AsyncMock()
    middleware = BanMiddleware()

    result = await middleware(
        handler,
        message,
        {"session": session, "event_from_user": message.from_user},
    )

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_banned_callback_is_ignored(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Banned User")
    await set_user_banned(session, user)
    callback = make_callback()
    handler = AsyncMock()
    middleware = BanMiddleware()

    result = await middleware(
        handler,
        callback,
        {"session": session, "event_from_user": callback.from_user},
    )

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_banned_user_is_resolved_from_event(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Banned User")
    await set_user_banned(session, user)
    message = make_message(text="/start")
    handler = AsyncMock()
    middleware = BanMiddleware()

    result = await middleware(
        handler,
        message,
        {"session": session},
    )

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_allowed_message_reaches_handler(
    session: AsyncSession,
    make_message,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    message = make_message(text="/start")
    handler = AsyncMock(return_value="handled")
    middleware = BanMiddleware()
    data = {"session": session, "event_from_user": message.from_user}

    result = await middleware(handler, message, data)

    assert result == "handled"
    handler.assert_awaited_once_with(message, data)


@pytest.mark.asyncio
async def test_unknown_user_reaches_handler(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/start")
    handler = AsyncMock(return_value="handled")
    middleware = BanMiddleware()

    result = await middleware(
        handler,
        message,
        {"session": session, "event_from_user": message.from_user},
    )

    assert result == "handled"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_event_without_user_reaches_handler(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/start")
    message.from_user = None
    handler = AsyncMock(return_value="handled")
    middleware = BanMiddleware()

    result = await middleware(handler, message, {"session": session})

    assert result == "handled"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_hid_failure_ignores_update(
    session: AsyncSession,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_telegram_id: int) -> str:
        raise HIDError("HID is unavailable")

    monkeypatch.setattr("app.middlewares.telegram_id_to_hid", fail)
    message = make_message(text="/start")
    handler = AsyncMock()
    middleware = BanMiddleware()

    result = await middleware(
        handler,
        message,
        {"session": session, "event_from_user": message.from_user},
    )

    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_session_raises(
    make_message,
) -> None:
    message = make_message(text="/start")
    handler = AsyncMock()
    middleware = BanMiddleware()

    with pytest.raises(RuntimeError):
        await middleware(handler, message, {})
