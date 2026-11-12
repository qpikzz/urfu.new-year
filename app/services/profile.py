"""Profile step helpers for registration (FLOWS 2)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.db.enums import ParticipantStatus

TIMEZONE_MIN = -12
TIMEZONE_MAX = 14
TEST_INSTITUTES = ("ИРИТ-РТФ", "ИнЭУ", "ГУК")

_TIMEZONE_PATTERN = re.compile(r"^[+-]?\d+$")


def parse_timezone(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if _TIMEZONE_PATTERN.fullmatch(text) is None:
        return None
    offset = int(text)
    if TIMEZONE_MIN <= offset <= TIMEZONE_MAX:
        return offset
    return None


def institute_options(
    configured: Sequence[str] | None,
) -> tuple[str, ...]:
    if configured:
        return tuple(configured)
    return TEST_INSTITUTES


def parse_status(value: str) -> ParticipantStatus | None:
    try:
        return ParticipantStatus(value)
    except ValueError:
        return None


def parse_institute(
    value: str,
    institutes: Sequence[str],
) -> str | None:
    try:
        index = int(value)
    except ValueError:
        return None
    if 0 <= index < len(institutes):
        return institutes[index]
    return None


__all__ = [
    "TEST_INSTITUTES",
    "TIMEZONE_MAX",
    "TIMEZONE_MIN",
    "institute_options",
    "parse_institute",
    "parse_status",
    "parse_timezone",
]
