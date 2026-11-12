"""Shared rendering of the participant profile text (MESSAGES 7.2)."""

from __future__ import annotations

from app.content import texts
from app.db.enums import CircleStatus
from app.db.models import Circle, User


def _circle_status_label(circle: Circle) -> str:
    if circle.is_buffered and circle.status == CircleStatus.APPROVED:
        return texts.BUFFERED_CIRCLE_STATUS_LABEL
    return texts.CIRCLE_STATUS_LABELS[CircleStatus(circle.status)]


def build_menu_text(user: User, circle: Circle | None = None) -> str:
    if not (
        user.registered_at is not None
        and user.status is not None
        and user.timezone is not None
    ):
        raise ValueError("registration is not complete")

    status_label = texts.PARTICIPANT_STATUS_LABELS[user.status]
    timezone_label = texts.format_timezone(user.timezone)

    if circle is None:
        return texts.format_menu(
            registered_at=texts.format_date(user.registered_at, user.timezone),
            status=status_label,
            institute=user.institute,
            timezone=timezone_label,
        )

    circle_status = CircleStatus(circle.status)
    rejection_reason = None
    if circle_status == CircleStatus.REJECTED and circle.rejection_reason:
        rejection_reason = texts.REJECTION_REASON_LABELS[circle.rejection_reason]

    return texts.format_menu(
        registered_at=texts.format_date(user.registered_at, user.timezone),
        status=status_label,
        institute=user.institute,
        timezone=timezone_label,
        cir_id=circle.id,
        circle_status=_circle_status_label(circle),
        duration=circle.duration,
        sent_at=texts.format_date(circle.sent_at, user.timezone),
        rejection_reason=rejection_reason,
    )


__all__ = ["build_menu_text"]
