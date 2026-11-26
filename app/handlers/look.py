"""Handler for /look."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.texts import format_look_not_found
from app.db.requests import get_circle
from app.services import parse_cir_id

logger = logging.getLogger(__name__)

router = Router(name="look")


@router.message(Command("look"))
async def handle_look(message: Message, session: AsyncSession) -> None:
    cir_id = parse_cir_id(message.text)
    if cir_id is None:
        return

    circle = await get_circle(session, cir_id)
    if circle is None:
        await message.answer(format_look_not_found(cir_id))
        logger.info("Look requested, circle not found: cir_id=%s", cir_id)
        return

    await message.answer_video_note(video_note=circle.file_id)
    logger.info(
        "Look requested: cir_id=%s owner_hid=%s",
        circle.id,
        circle.owner_hid,
    )


__all__ = ["handle_look", "router"]
