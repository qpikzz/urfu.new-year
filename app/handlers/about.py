"""Handler for /about."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.requests import get_circle, get_user
from app.services import build_menu_text, command_argument, is_registration_complete

logger = logging.getLogger(__name__)

router = Router(name="about")


@router.message(Command("about"))
async def handle_about(message: Message, session: AsyncSession) -> None:
    hid = command_argument(message.text)
    if hid is None:
        return

    user = await get_user(session, hid)
    if user is None or not is_registration_complete(user):
        return

    circle = (
        await get_circle(session, user.cir_id)
        if user.cir_id is not None
        else None
    )
    await message.answer(build_menu_text(user, circle))
    logger.info("About shown: hid=%s", user.hid)


__all__ = ["handle_about", "router"]
