"""Handlers for the manual announcement command (FLOWS 12.1)."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content import texts
from app.db.requests import get_all_users
from app.services import resolve_admin_hid, send_announcement

logger = logging.getLogger(__name__)

router = Router(name="send")

YEKATERINBURG_OFFSET = 5


class AnnouncementStates(StatesGroup):
    awaiting_message = State()


@router.message(Command("send"))
async def handle_send(
    message: Message,
    state: FSMContext,
    config: Config | None = None,
) -> None:
    admin_hid = resolve_admin_hid(message.from_user, config)
    if admin_hid is None:
        return

    await state.set_state(AnnouncementStates.awaiting_message)
    await message.answer(texts.SEND_ASK)
    logger.info("Announcement requested: admin_hid=%s", admin_hid)


@router.message(StateFilter(AnnouncementStates.awaiting_message))
async def handle_announcement(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config | None = None,
) -> None:
    if message.text is not None and message.text.startswith("/"):
        raise SkipHandler

    admin_hid = resolve_admin_hid(message.from_user, config)
    if admin_hid is None or message.chat is None:
        return

    await state.clear()
    await message.answer(texts.SEND_STARTED)

    users = await get_all_users(session)
    mailing = await send_announcement(
        session,
        bot,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        users=users,
    )
    await message.answer(
        texts.format_send_done(
            sent=mailing.sent_count,
            received=mailing.received_count,
            started=texts.format_time(
                mailing.started_at,
                YEKATERINBURG_OFFSET,
            ),
            finished=texts.format_time(
                mailing.finished_at,
                YEKATERINBURG_OFFSET,
            ),
        )
    )
    logger.info(
        "Announcement finished: admin_hid=%s sent=%s received=%s",
        admin_hid,
        mailing.sent_count,
        mailing.received_count,
    )


__all__ = ["AnnouncementStates", "handle_announcement", "handle_send", "router"]
