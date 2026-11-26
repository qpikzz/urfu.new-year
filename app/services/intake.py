"""Intake closure state and administrator notifications (FLOWS 9)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content import texts
from app.db.requests import get_setting, set_setting

logger = logging.getLogger(__name__)

MANUAL_CLOSE_SETTING_KEY = "intake_closed_manual"
YEKATERINBURG_OFFSET = 5


class IntakeReason(StrEnum):
    MANUAL = "manual"
    ENVIRONMENT = "environment"
    CPU = "cpu"
    DISK = "disk"
    QUEUE = "queue"


@dataclass(frozen=True, slots=True)
class IntakeClosure:
    reason: IntakeReason
    label: str


_automatic_closures: dict[IntakeReason, str] = {}


def reset_automatic_closures() -> None:
    _automatic_closures.clear()


def automatic_closures() -> tuple[IntakeClosure, ...]:
    return tuple(
        IntakeClosure(reason, label)
        for reason, label in _automatic_closures.items()
    )


async def is_manual_closed(session: AsyncSession) -> bool:
    return await get_setting(session, MANUAL_CLOSE_SETTING_KEY) == "true"


async def set_manual_closed(
    session: AsyncSession,
    closed: bool,
) -> None:
    await set_setting(
        session,
        MANUAL_CLOSE_SETTING_KEY,
        "true" if closed else "false",
    )


async def active_closures(
    session: AsyncSession,
    config: Config | None,
) -> tuple[IntakeClosure, ...]:
    closures: list[IntakeClosure] = []
    if config is not None and config.intake_closed:
        closures.append(
            IntakeClosure(
                IntakeReason.ENVIRONMENT,
                texts.TEXTS["intake.reason.environment"],
            )
        )
    if await is_manual_closed(session):
        closures.append(
            IntakeClosure(
                IntakeReason.MANUAL,
                texts.TEXTS["intake.reason.manual"],
            )
        )
    closures.extend(automatic_closures())
    return tuple(closures)


async def is_intake_closed(
    session: AsyncSession,
    config: Config | None,
) -> bool:
    return bool(await active_closures(session, config))


def intake_closed_message(config: Config | None) -> str:
    channel_url = config.channel_url if config and config.channel_url else ""
    return texts.format_intake_closed(channel_url=channel_url)


def _admin_time(now: datetime | None) -> str:
    return texts.format_time(
        now or datetime.now(UTC),
        YEKATERINBURG_OFFSET,
    )


async def notify_intake_closed(
    bot: Bot | None,
    config: Config | None,
    closure: IntakeClosure,
    *,
    now: datetime | None = None,
) -> bool:
    if bot is None or config is None or config.admin_chat_id is None:
        logger.warning(
            "Intake closure notification skipped, admin chat is not configured: "
            "reason=%s",
            closure.reason,
        )
        return False

    try:
        await bot.send_message(
            chat_id=config.admin_chat_id,
            text=texts.format_intake_admin_closed(
                time=_admin_time(now),
                reason=closure.label,
            ),
        )
    except Exception:
        logger.exception(
            "Failed to notify administrators about intake closure: reason=%s",
            closure.reason,
        )
        return False

    logger.info("Intake closure notified: reason=%s", closure.reason)
    return True


async def notify_intake_reopened(
    bot: Bot | None,
    config: Config | None,
    closure: IntakeClosure,
    *,
    now: datetime | None = None,
) -> bool:
    if bot is None or config is None or config.admin_chat_id is None:
        logger.warning(
            "Intake reopening notification skipped, admin chat is not configured: "
            "reason=%s",
            closure.reason,
        )
        return False

    try:
        await bot.send_message(
            chat_id=config.admin_chat_id,
            text=texts.format_intake_admin_reopened(
                time=_admin_time(now),
                reason=closure.label,
            ),
        )
    except Exception:
        logger.exception(
            "Failed to notify administrators about intake reopening: reason=%s",
            closure.reason,
        )
        return False

    logger.info("Intake reopening notified: reason=%s", closure.reason)
    return True


async def notify_environment_closure(
    bot: Bot | None,
    config: Config | None,
    *,
    now: datetime | None = None,
) -> bool:
    if config is None or not config.intake_closed:
        return False
    return await notify_intake_closed(
        bot,
        config,
        IntakeClosure(
            IntakeReason.ENVIRONMENT,
            texts.TEXTS["intake.reason.environment"],
        ),
        now=now,
    )


async def toggle_manual_closure(
    session: AsyncSession,
    *,
    bot: Bot | None = None,
    config: Config | None = None,
) -> bool:
    was_closed = await is_intake_closed(session, config)
    new_state = not await is_manual_closed(session)
    await set_manual_closed(session, new_state)

    now_closed = await is_intake_closed(session, config)
    if not was_closed and now_closed:
        await notify_intake_closed(
            bot,
            config,
            IntakeClosure(
                IntakeReason.MANUAL,
                texts.TEXTS["intake.reason.manual"],
            ),
        )
    elif was_closed and not now_closed:
        await notify_intake_reopened(
            bot,
            config,
            IntakeClosure(
                IntakeReason.MANUAL,
                texts.TEXTS["intake.reason.manual"],
            ),
        )

    return new_state


async def apply_automatic_closure(
    session: AsyncSession,
    bot: Bot | None,
    config: Config | None,
    closure: IntakeClosure,
) -> bool:
    was_closed = await is_intake_closed(session, config)
    _automatic_closures[closure.reason] = closure.label

    now_closed = await is_intake_closed(session, config)
    if not was_closed and now_closed:
        await notify_intake_closed(bot, config, closure)
        return True
    return False


async def remove_automatic_closure(
    session: AsyncSession,
    bot: Bot | None,
    config: Config | None,
    reason: IntakeReason,
) -> bool:
    label = _automatic_closures.pop(reason, None)
    if label is None:
        return False
    closure = IntakeClosure(reason, label)

    if not await is_intake_closed(session, config):
        await notify_intake_reopened(bot, config, closure)
        return True
    return False


__all__ = [
    "MANUAL_CLOSE_SETTING_KEY",
    "YEKATERINBURG_OFFSET",
    "IntakeClosure",
    "IntakeReason",
    "active_closures",
    "apply_automatic_closure",
    "automatic_closures",
    "intake_closed_message",
    "is_intake_closed",
    "is_manual_closed",
    "notify_environment_closure",
    "notify_intake_closed",
    "notify_intake_reopened",
    "remove_automatic_closure",
    "reset_automatic_closures",
    "set_manual_closed",
    "toggle_manual_closure",
]
