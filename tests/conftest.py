from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.types import CallbackQuery, Message, Update
from aiogram.types import User as TelegramUser
from sqlalchemy import text
from sqlalchemy.dialects import sqlite
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateTable

from app.db import Base
from app.db.models import Circle, Setting, User
from app.logging_setup import reset_logging


@pytest.fixture(autouse=True)
def reset_application_logging() -> None:
    yield
    reset_logging()


def _create_sqlite_schema(sync_connection) -> None:
    Base.metadata.create_all(
        sync_connection,
        tables=[User.__table__, Setting.__table__],
    )
    ddl = str(CreateTable(Circle.__table__).compile(dialect=sqlite.dialect()))
    # SQLite has no identity columns; INTEGER PRIMARY KEY autoincrements.
    ddl = ddl.replace("id BIGINT NOT NULL", "id INTEGER NOT NULL")
    sync_connection.execute(text(ddl))


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(_create_sqlite_schema)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session


@pytest.fixture
def bot() -> AsyncMock:
    return AsyncMock(spec=Bot)


@pytest.fixture
def telegram_user() -> MagicMock:
    user = MagicMock(spec=TelegramUser)
    user.id = 1001
    user.full_name = "Test User"
    user.username = "test_user"
    return user


@pytest.fixture
def make_message(
    telegram_user: MagicMock,
) -> Callable[..., MagicMock]:
    def factory(
        *,
        text: str | None = None,
        from_user: MagicMock | None = None,
    ) -> MagicMock:
        message = MagicMock(spec=Message)
        message.message_id = 1
        message.text = text
        message.caption = None
        message.from_user = from_user or telegram_user
        message.chat = MagicMock()
        message.answer = AsyncMock()
        message.answer_video_note = AsyncMock()
        message.reply = AsyncMock()
        message.edit_text = AsyncMock()
        message.edit_reply_markup = AsyncMock()
        return message

    return factory


@pytest.fixture
def message(make_message: Callable[..., MagicMock]) -> MagicMock:
    return make_message()


@pytest.fixture
def make_callback(
    telegram_user: MagicMock,
    make_message: Callable[..., MagicMock],
) -> Callable[..., MagicMock]:
    def factory(
        *,
        data: str = "test:callback",
        message: MagicMock | None = None,
        from_user: MagicMock | None = None,
    ) -> MagicMock:
        callback = MagicMock(spec=CallbackQuery)
        callback.id = "callback-id"
        callback.data = data
        callback.from_user = from_user or telegram_user
        callback.message = message or make_message()
        callback.answer = AsyncMock()
        return callback

    return factory


@pytest.fixture
def callback_query(make_callback: Callable[..., MagicMock]) -> MagicMock:
    return make_callback()


@pytest.fixture
def make_update(
    make_message: Callable[..., MagicMock],
    make_callback: Callable[..., MagicMock],
) -> Callable[..., MagicMock]:
    def factory(
        *,
        message: MagicMock | None = None,
        callback_query: MagicMock | None = None,
        update_id: int = 1,
    ) -> MagicMock:
        update = MagicMock(spec=Update)
        update.update_id = update_id
        update.message = message
        update.callback_query = callback_query
        update.effective_message = message or (
            callback_query.message if callback_query is not None else None
        )
        update.effective_user = (
            message.from_user
            if message is not None
            else callback_query.from_user
            if callback_query is not None
            else None
        )
        return update

    return factory


@pytest.fixture
def update(
    make_update: Callable[..., MagicMock],
    message: MagicMock,
) -> MagicMock:
    return make_update(message=message)
