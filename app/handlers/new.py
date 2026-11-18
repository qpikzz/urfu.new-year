"""Handler for /new."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content.texts import NEW_ASK, NEW_NO_CIRCLE, NEW_UNAVAILABLE
from app.db.requests import get_circle, get_user
from app.handlers.start import send_registration_step
from app.hid import HIDError, telegram_id_to_hid
from app.services import (
    AWAITING_NEW_CIRCLE_KEY,
    is_circle_in_progress,
    is_registration_complete,
    resume_registration,
)

logger = logging.getLogger(__name__)

router = Router(name="new")


@router.message(Command("new"))
async def handle_new(
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
        logger.error("New command aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is None or user.is_banned:
        return

    if not is_registration_complete(user):
        await state.update_data({AWAITING_NEW_CIRCLE_KEY: False})
        step = await resume_registration(state, user)
        await send_registration_step(message, state, config, step)
        logger.info(
            "New command continued registration: hid=%s step=%s",
            user.hid,
            step.value,
        )
        return

    circle = (
        await get_circle(session, user.cir_id)
        if user.cir_id is not None
        else None
    )
    if circle is None:
        await state.update_data({AWAITING_NEW_CIRCLE_KEY: False})
        await message.answer(NEW_NO_CIRCLE)
        logger.info("New command without circle: hid=%s", user.hid)
        return

    if is_circle_in_progress(circle):
        await state.update_data({AWAITING_NEW_CIRCLE_KEY: False})
        await message.answer(NEW_UNAVAILABLE)
        logger.info(
            "New command unavailable: hid=%s cir_id=%s",
            user.hid,
            circle.id,
        )
        return

    await state.update_data({AWAITING_NEW_CIRCLE_KEY: True})
    await message.answer(NEW_ASK)
    logger.info(
        "New circle requested: hid=%s cir_id=%s",
        user.hid,
        circle.id,
    )


__all__ = ["handle_new", "router"]
