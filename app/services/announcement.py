"""Manual announcement delivery (FLOWS 12.1, DATA 4)."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Mailing, User
from app.db.requests import create_mailing, finish_mailing
from app.hid import HIDError, hid_to_telegram_id

logger = logging.getLogger(__name__)

MAILING_MESSAGES_PER_SECOND = 8
MAILING_DELAY_SECONDS = 1 / MAILING_MESSAGES_PER_SECOND


async def send_announcement(
    session: AsyncSession,
    bot: Bot,
    *,
    from_chat_id: int,
    message_id: int,
    users: list[User],
) -> Mailing:
    """Copy one message to every participant and record the mailing run.

    Attempts are counted in ``sent_count``; only successful deliveries are
    counted in ``received_count`` and ``received_hids``. Nothing is retried.
    """
    mailing = await create_mailing(session)
    sent_count = 0
    received_count = 0
    received_hids: list[str] = []

    for index, user in enumerate(users):
        if index:
            await asyncio.sleep(MAILING_DELAY_SECONDS)

        sent_count += 1

        try:
            chat_id = hid_to_telegram_id(user.hid)
        except HIDError:
            logger.error("Announcement skipped, invalid HID: hid=%s", user.hid)
            continue

        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
        except Exception as exc:
            logger.warning(
                "Announcement not delivered: hid=%s reason=%s",
                user.hid,
                type(exc).__name__,
            )
            continue

        received_count += 1
        received_hids.append(user.hid)

    return await finish_mailing(
        session,
        mailing,
        sent_count=sent_count,
        received_count=received_count,
        received_hids=received_hids,
    )


__all__ = [
    "MAILING_DELAY_SECONDS",
    "MAILING_MESSAGES_PER_SECOND",
    "send_announcement",
]
