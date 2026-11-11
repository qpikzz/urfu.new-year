from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.requests import create_circle, create_user

pytestmark = pytest.mark.asyncio


async def test_session_starts_with_empty_tables(session: AsyncSession) -> None:
    users = await session.scalar(select(func.count()).select_from(User))

    assert users == 0


async def test_session_persists_and_flushes_models(session: AsyncSession) -> None:
    user = await create_user(session, hid="hid-1", full_name="Test User")

    assert await session.get(User, "hid-1") is user
    assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_test_database_supports_autoincremented_circles(
    session: AsyncSession,
) -> None:
    await create_user(session, hid="hid-1", full_name="Test User")

    circle = await create_circle(
        session,
        owner_hid="hid-1",
        file_id="file-id",
        duration=10,
    )

    assert circle.id > 0


async def test_database_is_fresh_for_each_test(session: AsyncSession) -> None:
    assert await session.get(User, "shared-hid") is None

    await create_user(session, hid="shared-hid", full_name="First Test")


async def test_bot_mock_awaits_async_methods(bot: AsyncMock) -> None:
    result = await bot.send_message(chat_id=1, text="test")

    bot.send_message.assert_awaited_once_with(chat_id=1, text="test")
    assert result is not None


async def test_message_factory_sets_content_and_async_methods(
    make_message,
) -> None:
    message = make_message(text="hello")

    await message.answer("answer")
    await message.reply("reply")

    assert message.text == "hello"
    message.answer.assert_awaited_once_with("answer")
    message.reply.assert_awaited_once_with("reply")


async def test_callback_mock_has_async_answer(callback_query) -> None:
    await callback_query.answer()

    assert callback_query.data == "test:callback"
    callback_query.answer.assert_awaited_once_with()


async def test_update_factory_wires_message(
    make_update,
    message,
) -> None:
    update = make_update(message=message)

    assert update.message is message
    assert update.effective_message is message
    assert update.effective_user is message.from_user


async def test_update_factory_wires_callback(
    make_update,
    callback_query,
) -> None:
    update = make_update(callback_query=callback_query)

    assert update.callback_query is callback_query
    assert update.effective_message is callback_query.message
    assert update.effective_user is callback_query.from_user
