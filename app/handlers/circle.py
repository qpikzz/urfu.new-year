"""Handlers for circle submission (FLOWS 4)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.texts import (
    CIRCLE_DURATION_INVALID,
    CIRCLE_IN_PROGRESS,
    CIRCLE_QUEUED,
    CIRCLE_WRONG_TYPE,
    NEW_ASK,
)
from app.db.enums import CircleStatus
from app.db.models import Circle, User
from app.db.requests import (
    create_circle,
    get_circle,
    get_user,
    set_user_circle,
)
from app.hid import HIDError, telegram_id_to_hid
from app.services import (
    is_circle_in_progress,
    is_registration_complete,
    is_valid_circle_duration,
)

logger = logging.getLogger(__name__)

router = Router(name="circle")


async def _get_participant(
    message: Message,
    session: AsyncSession,
) -> User | None:
    telegram_user = message.from_user
    if telegram_user is None:
        return None
    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Circle intake aborted: HID encoding failed")
        return None

    user = await get_user(session, hid)
    if user is None or user.is_banned:
        return None
    return user


async def _get_latest_circle(
    session: AsyncSession,
    user: User,
) -> Circle | None:
    if user.cir_id is None:
        return None
    return await get_circle(session, user.cir_id)


@router.message(F.video_note)
async def handle_video_note(
    message: Message,
    session: AsyncSession,
) -> None:
    user = await _get_participant(message, session)
    if user is None or not is_registration_complete(user):
        return

    video_note = message.video_note
    if video_note is None:
        return

    duration = video_note.duration
    if not is_valid_circle_duration(duration):
        await message.answer(CIRCLE_DURATION_INVALID)
        logger.info(
            "Circle duration invalid: hid=%s duration=%s",
            user.hid,
            duration,
        )
        return

    latest = await _get_latest_circle(session, user)
    if latest is not None:
        if is_circle_in_progress(latest):
            await message.answer(CIRCLE_IN_PROGRESS)
            logger.info(
                "Circle declined, previous in progress: hid=%s cir_id=%s",
                user.hid,
                latest.id,
            )
            return

        await message.answer(NEW_ASK)
        logger.info(
            "Circle declined, /new required: hid=%s cir_id=%s",
            user.hid,
            latest.id,
        )
        return

    circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id=video_note.file_id,
        duration=duration,
        status=CircleStatus.PENDING_AUTO,
    )
    await set_user_circle(session, user, circle.id)
    await message.answer(CIRCLE_QUEUED)
    logger.info(
        "Circle queued: hid=%s cir_id=%s duration=%s",
        user.hid,
        circle.id,
        duration,
    )


@router.message(~F.video_note)
async def handle_other_content(
    message: Message,
    session: AsyncSession,
) -> None:
    if message.text is not None and message.text.startswith("/"):
        raise SkipHandler

    user = await _get_participant(message, session)
    if user is None or not is_registration_complete(user):
        raise SkipHandler

    latest = await _get_latest_circle(session, user)
    if is_circle_in_progress(latest):
        return

    await message.answer(CIRCLE_WRONG_TYPE)
    logger.info("Non-circle content declined: hid=%s", user.hid)


__all__ = ["handle_other_content", "handle_video_note", "router"]
