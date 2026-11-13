"""Circle submission rules (FLOWS 4)."""

from __future__ import annotations

from app.db.enums import CircleStatus
from app.db.models import Circle

MIN_CIRCLE_DURATION = 3
MAX_CIRCLE_DURATION = 30

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


__all__ = [
    "MAX_CIRCLE_DURATION",
    "MIN_CIRCLE_DURATION",
    "PROCESSING_STATUSES",
    "is_circle_in_progress",
    "is_valid_circle_duration",
]
