"""Handler for /close."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content.texts import CLOSE_OFF, CLOSE_ON
from app.services import toggle_manual_closure

logger = logging.getLogger(__name__)

router = Router(name="close")


@router.message(Command("close"))
async def handle_close(
    message: Message,
    session: AsyncSession,
    bot: Bot,
    config: Config | None = None,
) -> None:
    closed = await toggle_manual_closure(
        session,
        bot=bot,
        config=config,
    )
    await message.answer(CLOSE_ON if closed else CLOSE_OFF)
    logger.info("Manual intake closure toggled: closed=%s", closed)


__all__ = ["handle_close", "router"]
