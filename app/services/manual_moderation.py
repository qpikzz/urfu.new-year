"""Manual moderation flow (FLOWS 6)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Config
from app.db.enums import RejectionReason
from app.db.models import Circle
from app.db.requests import (
    delete_setting,
    get_circles_pending_manual,
    get_setting,
    set_setting,
)
from app.keyboards import (
    MODERATION_APPROVE_ACTION,
    MODERATION_CALLBACK_PREFIX,
    MODERATION_CANCEL_ACTION,
    MODERATION_REJECT_ACTION,
    moderation_keyboard,
)
from app.services.admin_access import is_admin_hid

logger = logging.getLogger(__name__)

MANUAL_MODERATION_POLL_INTERVAL = 5.0
_REVIEW_MARKER_PREFIX = "manual_moderation_sent:"
_MARKER_SENDING = "sending"
_MARKER_SENT = "sent"

_dispatching: set[int] = set()


class ModerationAction(StrEnum):
    APPROVE = MODERATION_APPROVE_ACTION
    REJECT = MODERATION_REJECT_ACTION
    CANCEL = MODERATION_CANCEL_ACTION


@dataclass(frozen=True, slots=True)
class ModerationCallback:
    action: ModerationAction
    cir_id: int
    reason: RejectionReason | None = None


def review_marker_key(cir_id: int) -> str:
    return f"{_REVIEW_MARKER_PREFIX}{cir_id}"


def _parse_cir_id(value: str) -> int | None:
    try:
        cir_id = int(value)
    except ValueError:
        return None
    return cir_id if cir_id > 0 else None


def parse_moderation_callback(data: str | None) -> ModerationCallback | None:
    if not data or not data.startswith(MODERATION_CALLBACK_PREFIX):
        return None

    parts = data.removeprefix(MODERATION_CALLBACK_PREFIX).split(":")
    if len(parts) == 2:
        action_value, cir_id_value = parts
        cir_id = _parse_cir_id(cir_id_value)
        if cir_id is None:
            return None
        if action_value == MODERATION_REJECT_ACTION:
            return ModerationCallback(ModerationAction.REJECT, cir_id)
        if action_value == MODERATION_APPROVE_ACTION:
            return ModerationCallback(ModerationAction.APPROVE, cir_id)
        if action_value == MODERATION_CANCEL_ACTION:
            return ModerationCallback(ModerationAction.CANCEL, cir_id)
        return None

    if len(parts) == 3:
        action_value, cir_id_value, reason_value = parts
        if action_value != MODERATION_REJECT_ACTION:
            return None
        cir_id = _parse_cir_id(cir_id_value)
        if cir_id is None:
            return None
        try:
            reason = RejectionReason(reason_value)
        except ValueError:
            return None
        return ModerationCallback(ModerationAction.REJECT, cir_id, reason)

    return None


async def is_circle_sent_for_review(
    session: AsyncSession,
    cir_id: int,
) -> bool:
    marker = await get_setting(session, review_marker_key(cir_id))
    return marker is not None


async def clear_review_marker(session: AsyncSession, cir_id: int) -> None:
    await delete_setting(session, review_marker_key(cir_id))


async def send_circle_for_review(
    bot: Bot,
    session: AsyncSession,
    circle: Circle,
    config: Config | None,
) -> bool:
    """Send a circle to the administrators' chat at most once."""
    if config is None or config.admin_chat_id is None:
        logger.warning(
            "Manual moderation skipped, admin chat is not configured: cir_id=%s",
            circle.id,
        )
        return False

    if circle.id in _dispatching:
        return False

    marker_key = review_marker_key(circle.id)
    _dispatching.add(circle.id)
    if await get_setting(session, marker_key) is not None:
        _dispatching.discard(circle.id)
        return False

    await set_setting(session, marker_key, _MARKER_SENDING)
    try:
        await bot.send_video_note(
            chat_id=config.admin_chat_id,
            video_note=circle.file_id,
            reply_markup=moderation_keyboard(circle.id),
        )
    except Exception:
        _dispatching.discard(circle.id)
        await delete_setting(session, marker_key)
        raise

    _dispatching.discard(circle.id)
    await set_setting(session, marker_key, _MARKER_SENT)
    logger.info(
        "Circle sent to manual moderation: cir_id=%s owner_hid=%s",
        circle.id,
        circle.owner_hid,
    )
    return True


async def send_pending_circles(
    bot: Bot,
    session: AsyncSession,
    config: Config | None,
) -> int:
    if config is None or config.admin_chat_id is None:
        return 0

    sent = 0
    for circle in await get_circles_pending_manual(session):
        try:
            if await send_circle_for_review(bot, session, circle, config):
                sent += 1
        except Exception:
            logger.exception(
                "Failed to send circle to manual moderation: cir_id=%s",
                circle.id,
            )
    return sent


async def run_manual_moderation_worker(
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot,
    config: Config | None,
    *,
    interval: float = MANUAL_MODERATION_POLL_INTERVAL,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Periodically forward circles that reached manual moderation."""
    while stop_event is None or not stop_event.is_set():
        try:
            async with session_factory() as session:
                await send_pending_circles(bot, session, config)
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Manual moderation worker iteration failed")

        if stop_event is None:
            await asyncio.sleep(interval)
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            pass


__all__ = [
    "MANUAL_MODERATION_POLL_INTERVAL",
    "ModerationAction",
    "ModerationCallback",
    "clear_review_marker",
    "is_admin_hid",
    "is_circle_sent_for_review",
    "parse_moderation_callback",
    "review_marker_key",
    "run_manual_moderation_worker",
    "send_circle_for_review",
    "send_pending_circles",
]
