"""Aiogram middlewares shared by handlers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.requests import get_user
from app.hid import HIDError, telegram_id_to_hid
from app.services.admin_access import (
    admin_command_from_text,
    resolve_admin_hid,
)

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Provide one database session per update and manage its transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            return result


class BanMiddleware(BaseMiddleware):
    """Ignore updates from participants who are banned."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession | None = data.get("session")
        if session is None:
            raise RuntimeError("Database session is not available")

        telegram_user = data.get("event_from_user") or getattr(
            event,
            "from_user",
            None,
        )
        if telegram_user is None:
            return await handler(event, data)

        try:
            hid = telegram_id_to_hid(telegram_user.id)
        except HIDError:
            logger.error("Ban check aborted: HID encoding failed")
            return None

        user = await get_user(session, hid)
        if user is not None and user.is_banned:
            logger.info("Banned update ignored: hid=%s", user.hid)
            return None

        return await handler(event, data)


class AdminAccessMiddleware(BaseMiddleware):
    """Silently ignore administrator commands from non-administrators."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        command = admin_command_from_text(event.text)
        if command is None:
            return await handler(event, data)

        telegram_user = data.get("event_from_user") or event.from_user
        if resolve_admin_hid(telegram_user, data.get("config")) is None:
            logger.info("Admin command ignored: command=%s", command)
            return None

        return await handler(event, data)


__all__ = [
    "AdminAccessMiddleware",
    "BanMiddleware",
    "DatabaseMiddleware",
]
