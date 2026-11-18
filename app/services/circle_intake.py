"""Circle submission rules (FLOWS 4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.db.enums import CircleStatus, RejectedBy
from app.db.models import Circle

MIN_CIRCLE_DURATION = 3
MAX_CIRCLE_DURATION = 30

AWAITING_NEW_CIRCLE_KEY = "awaiting_new_circle"

PROCESSING_STATUSES = frozenset(
    {
        CircleStatus.PENDING_AUTO,
        CircleStatus.PENDING_MANUAL,
    }
)


def is_valid_circle_duration(duration: int | None) -> bool:
    return (
        duration is not None
        and MIN_CIRCLE_DURATION <= duration <= MAX_CIRCLE_DURATION
    )


def is_circle_in_progress(circle: Circle | None) -> bool:
    return (
        circle is not None
        and CircleStatus(circle.status) in PROCESSING_STATUSES
    )


def is_awaiting_new_circle(state_data: Mapping[str, Any] | None) -> bool:
    return bool((state_data or {}).get(AWAITING_NEW_CIRCLE_KEY))


def was_manually_rejected(circle: Circle | None) -> bool:
    return (
        circle is not None
        and CircleStatus(circle.status) == CircleStatus.REJECTED
        and circle.rejected_by == RejectedBy.MANUAL
    )


__all__ = [
    "AWAITING_NEW_CIRCLE_KEY",
    "MAX_CIRCLE_DURATION",
    "MIN_CIRCLE_DURATION",
    "PROCESSING_STATUSES",
    "is_awaiting_new_circle",
    "is_circle_in_progress",
    "is_valid_circle_duration",
    "was_manually_rejected",
]
