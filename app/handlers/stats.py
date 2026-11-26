"""Handler for /stats."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import texts
from app.db.requests import get_statistics

logger = logging.getLogger(__name__)

router = Router(name="stats")


@router.message(Command("stats"))
async def handle_stats(message: Message, session: AsyncSession) -> None:
    statistics = await get_statistics(session)
    await message.answer(
        texts.format_stats(
            total_users=statistics.total_users,
            registered=statistics.registered_users,
            circles_total=statistics.circles_total,
            circles_today=statistics.circles_today,
            approved=statistics.approved,
            rejected_manual=statistics.rejected_manual,
            rejected_auto=statistics.rejected_auto,
        )
    )
    logger.info(
        "Stats shown: users=%s circles=%s",
        statistics.total_users,
        statistics.circles_total,
    )


__all__ = ["handle_stats", "router"]
