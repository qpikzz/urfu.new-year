"""Handler for /reject."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.texts import format_reject_done, format_status_not_found
from app.db.enums import RejectedBy, RejectionReason
from app.db.requests import get_circle, reject_circle
from app.services import parse_cir_id

logger = logging.getLogger(__name__)

router = Router(name="reject")


@router.message(Command("reject"))
async def handle_reject(message: Message, session: AsyncSession) -> None:
    cir_id = parse_cir_id(message.text)
    if cir_id is None:
        return

    circle = await get_circle(session, cir_id)
    if circle is None:
        await message.answer(format_status_not_found(cir_id))
        logger.info("Reject requested, circle not found: cir_id=%s", cir_id)
        return

    await reject_circle(
        session,
        circle,
        reason=RejectionReason.OTHER,
        rejected_by=RejectedBy.MANUAL,
    )
    await message.answer(format_reject_done(cir_id))
    logger.info(
        "Circle rejected by command: cir_id=%s owner_hid=%s",
        circle.id,
        circle.owner_hid,
    )


__all__ = ["handle_reject", "router"]
