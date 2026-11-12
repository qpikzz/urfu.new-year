"""Handler for /menu."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.db.requests import get_circle, get_user
from app.handlers.start import send_registration_step
from app.hid import HIDError, telegram_id_to_hid
from app.services import (
    build_menu_text,
    is_registration_complete,
    resume_registration,
)

logger = logging.getLogger(__name__)

router = Router(name="menu")


@router.message(Command("menu"))
async def handle_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    config: Config | None = None,
) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        return

    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Menu aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is None or user.is_banned:
        return

    if not is_registration_complete(user):
        step = await resume_registration(state, user)
        await send_registration_step(message, state, config, step)
        logger.info(
            "Menu resumed registration: hid=%s step=%s",
            user.hid,
            step.value,
        )
        return

    circle = (
        await get_circle(session, user.cir_id)
        if user.cir_id is not None
        else None
    )
    await message.answer(build_menu_text(user, circle))
    logger.info("Menu shown: hid=%s", user.hid)
