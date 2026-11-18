"""Aiogram application assembly and startup."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Config, ConfigError
from app.handlers import circle, menu, moderation, new, start
from app.middlewares import BanMiddleware, DatabaseMiddleware
from app.services import run_manual_moderation_worker


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def create_dispatcher(
    session_factory: async_sessionmaker[AsyncSession],
    config: Config | None = None,
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage(), config=config)
    database_middleware = DatabaseMiddleware(session_factory)
    ban_middleware = BanMiddleware()
    dispatcher.message.middleware(database_middleware)
    dispatcher.message.middleware(ban_middleware)
    dispatcher.callback_query.middleware(database_middleware)
    dispatcher.callback_query.middleware(ban_middleware)
    dispatcher.include_router(circle.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(menu.router)
    dispatcher.include_router(new.router)
    dispatcher.include_router(moderation.router)
    return dispatcher


async def run_bot(config: Config) -> None:
    if not config.database_url:
        raise ConfigError("DATABASE_URL is required to start the bot")

    engine = create_engine(config.database_url)
    session_factory = create_session_factory(engine)
    dispatcher = create_dispatcher(session_factory, config)
    bot = Bot(token=config.bot_token)
    moderation_worker: asyncio.Task[None] | None = None
    if config.admin_chat_id is not None:
        moderation_worker = asyncio.create_task(
            run_manual_moderation_worker(session_factory, bot, config)
        )
    try:
        await dispatcher.start_polling(bot)
    finally:
        if moderation_worker is not None:
            moderation_worker.cancel()
            with suppress(asyncio.CancelledError):
                await moderation_worker
        await bot.session.close()
        await engine.dispose()


__all__ = [
    "create_dispatcher",
    "create_engine",
    "create_session_factory",
    "run_bot",
]
