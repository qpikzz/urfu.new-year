"""Manual moderation callbacks (FLOWS 6)."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content.texts import (
    MODERATION_APPROVED,
    format_ban_manual_limit,
    format_manual_rejected,
)
from app.db.enums import CircleStatus, RejectionReason
from app.db.models import Circle
from app.db.requests import (
    decide_manual_circle,
    get_circle,
    get_user,
    set_user_banned,
)
from app.hid import HIDError, hid_to_telegram_id
from app.keyboards import (
    MODERATION_CALLBACK_PREFIX,
    rejection_reasons_keyboard,
)
from app.services import (
    ModerationAction,
    clear_review_marker,
    is_manual_resubmission_limit_reached,
    parse_moderation_callback,
    resolve_admin_hid,
)

logger = logging.getLogger(__name__)

router = Router(name="moderation")


async def _authorize(
    callback: CallbackQuery,
    config: Config | None,
) -> str | None:
    return resolve_admin_hid(callback.from_user, config)


async def _delete_message(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.delete()
    except Exception:
        logger.warning("Failed to delete manual moderation message")


async def _notify_participant(bot: Bot, circle: Circle, text: str) -> None:
    try:
        chat_id = hid_to_telegram_id(circle.owner_hid)
    except HIDError:
        logger.error(
            "Participant notification aborted: hid=%s cir_id=%s",
            circle.owner_hid,
            circle.id,
        )
        return

    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        logger.warning(
            "Participant notification failed: hid=%s cir_id=%s",
            circle.owner_hid,
            circle.id,
        )


async def _notify_manual_rejection(
    bot: Bot,
    session: AsyncSession,
    circle: Circle,
    reason: RejectionReason,
) -> None:
    user = await get_user(session, circle.owner_hid)
    if user is not None and user.is_banned:
        return

    if user is not None and is_manual_resubmission_limit_reached(user):
        await set_user_banned(session, user)
        logger.info(
            "Participant banned after repeated manual rejection: hid=%s "
            "cir_id=%s",
            user.hid,
            circle.id,
        )
        await _notify_participant(
            bot,
            circle,
            format_ban_manual_limit(reason=reason),
        )
        return

    await _notify_participant(
        bot,
        circle,
        format_manual_rejected(reason=reason),
    )


async def _show_rejection_reasons(
    callback: CallbackQuery,
    session: AsyncSession,
    cir_id: int,
) -> None:
    circle = await get_circle(session, cir_id)
    await callback.answer()
    if (
        circle is None
        or CircleStatus(circle.status) != CircleStatus.PENDING_MANUAL
    ):
        await _delete_message(callback)
        return

    if callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(
            reply_markup=rejection_reasons_keyboard(cir_id)
        )
    except Exception:
        logger.warning(
            "Failed to show rejection reasons: cir_id=%s",
            cir_id,
        )


@router.callback_query(F.data.startswith(MODERATION_CALLBACK_PREFIX))
async def handle_moderation_callback(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    config: Config | None = None,
) -> None:
    admin_hid = await _authorize(callback, config)
    if admin_hid is None:
        return

    parsed = parse_moderation_callback(callback.data)
    if parsed is None:
        return

    if parsed.action == ModerationAction.REJECT and parsed.reason is None:
        await _show_rejection_reasons(callback, session, parsed.cir_id)
        logger.info(
            "Manual rejection options requested: cir_id=%s admin_hid=%s",
            parsed.cir_id,
            admin_hid,
        )
        return

    approved = parsed.action in (
        ModerationAction.APPROVE,
        ModerationAction.CANCEL,
    )
    reason = parsed.reason
    circle = await decide_manual_circle(
        session,
        parsed.cir_id,
        approved=approved,
        reason=reason,
    )
    await callback.answer()

    if circle is None:
        await _delete_message(callback)
        logger.info(
            "Manual decision ignored, circle is not pending: cir_id=%s "
            "admin_hid=%s",
            parsed.cir_id,
            admin_hid,
        )
        return

    await _delete_message(callback)
    await clear_review_marker(session, circle.id)

    if approved:
        await _notify_participant(bot, circle, MODERATION_APPROVED)
        logger.info(
            "Manual moderation approved: cir_id=%s owner_hid=%s admin_hid=%s",
            circle.id,
            circle.owner_hid,
            admin_hid,
        )
        return

    if reason is None:
        return

    await _notify_manual_rejection(bot, session, circle, reason)
    logger.info(
        "Manual moderation rejected: cir_id=%s owner_hid=%s admin_hid=%s "
        "reason=%s",
        circle.id,
        circle.owner_hid,
        admin_hid,
        reason.value,
    )


__all__ = ["handle_moderation_callback", "router"]
