"""Moderation limits and bans (FLOWS 7)."""

from __future__ import annotations

from app.db.models import User

MANUAL_RESUBMISSIONS_LIMIT = 1


def is_manual_resubmission_limit_reached(user: User) -> bool:
    return user.resubmissions_used >= MANUAL_RESUBMISSIONS_LIMIT


__all__ = [
    "MANUAL_RESUBMISSIONS_LIMIT",
    "is_manual_resubmission_limit_reached",
]
