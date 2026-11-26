"""Handler for /accept."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.texts import format_accept_done, format_status_not_found
from app.db.requests import approve_circle, get_circle
from app.services import parse_cir_id

logger = logging.getLogger(__name__)

router = Router(name="accept")


@router.message(Command("accept"))
async def handle_accept(message: Message, session: AsyncSession) -> None:
    cir_id = parse_cir_id(message.text)
    if cir_id is None:
        return

    circle = await get_circle(session, cir_id)
    if circle is None:
        await message.answer(format_status_not_found(cir_id))
        logger.info("Accept requested, circle not found: cir_id=%s", cir_id)
        return

    await approve_circle(session, circle)
    await message.answer(format_accept_done(cir_id))
    logger.info(
        "Circle accepted by command: cir_id=%s owner_hid=%s",
        circle.id,
        circle.owner_hid,
    )


__all__ = ["handle_accept", "router"]
