"""Handler for /start."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.texts import START_WELCOME
from app.db.requests import (
    create_user,
    get_circle,
    get_user,
    update_user_identity,
)
from app.hid import HIDError, telegram_id_to_hid
from app.services import (
    build_menu_text,
    is_registration_complete,
    resume_registration,
)

logger = logging.getLogger(__name__)

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        return

    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Start flow aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is not None and user.is_banned:
        return

    full_name = telegram_user.full_name
    username = telegram_user.username or "0"
    if user is None:
        user = await create_user(
            session,
            hid=hid,
            full_name=full_name,
            username=username,
        )
    else:
        await update_user_identity(
            session,
            user,
            full_name=full_name,
            username=username,
        )

    if is_registration_complete(user):
        circle = await get_circle(session, user.cir_id) if user.cir_id else None
        await message.answer(build_menu_text(user, circle))
        logger.info("Start flow: hid=%s step=complete", user.hid)
        return

    step = await resume_registration(state, user)
    await message.answer(START_WELCOME)
    logger.info("Start flow: hid=%s step=%s", user.hid, step.value)
