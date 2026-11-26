"""Handler for /ban."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.texts import format_ban_done, format_ban_not_found
from app.db.requests import get_user, set_user_banned
from app.services import command_argument

logger = logging.getLogger(__name__)

router = Router(name="ban")


@router.message(Command("ban"))
async def handle_ban(message: Message, session: AsyncSession) -> None:
    hid = command_argument(message.text)
    if hid is None:
        return

    user = await get_user(session, hid)
    if user is None:
        await message.answer(format_ban_not_found(hid))
        logger.info("Ban requested, participant not found: hid=%s", hid)
        return

    await set_user_banned(session, user)
    await message.answer(format_ban_done(hid))
    logger.info("Participant banned by command: hid=%s", hid)


__all__ = ["handle_ban", "router"]
