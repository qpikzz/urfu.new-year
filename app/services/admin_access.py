"""Administrator identification and admin command access (FLOWS 1)."""

from __future__ import annotations

import logging

from aiogram.types import User as TelegramUser

from app.config import Config
from app.hid import HIDError, telegram_id_to_hid

logger = logging.getLogger(__name__)

ADMIN_COMMANDS = frozenset(
    {
        "about",
        "accept",
        "ban",
        "close",
        "look",
        "reject",
        "send",
        "stats",
    }
)


def is_admin_hid(hid: str | None, config: Config | None) -> bool:
    return bool(hid and config is not None and hid in config.admin_hids)


def resolve_admin_hid(
    telegram_user: TelegramUser | None,
    config: Config | None,
) -> str | None:
    if telegram_user is None:
        return None

    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Admin check aborted: HID encoding failed")
        return None

    return hid if is_admin_hid(hid, config) else None


def admin_command_from_text(text: str | None) -> str | None:
    if not text:
        return None

    tokens = text.lstrip().split(maxsplit=1)
    if not tokens:
        return None

    first_token = tokens[0]
    if not first_token.startswith("/"):
        return None

    command = first_token[1:].split("@", 1)[0].lower()
    return command if command in ADMIN_COMMANDS else None


def is_admin_command(text: str | None) -> bool:
    return admin_command_from_text(text) is not None


__all__ = [
    "ADMIN_COMMANDS",
    "admin_command_from_text",
    "is_admin_command",
    "is_admin_hid",
    "resolve_admin_hid",
]
