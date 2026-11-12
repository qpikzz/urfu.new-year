"""Registration progress resolution and resumption (FLOWS 2)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from aiogram.fsm.context import FSMContext

from app.db.enums import ParticipantStatus
from app.db.models import User

CAPTCHA_PASSED_KEY = "captcha_passed"
CONSENT_ACCEPTED_KEY = "consent_accepted"
REGISTRATION_STEP_KEY = "registration_step"

INSTITUTE_REQUIRED_STATUSES = frozenset(
    {
        ParticipantStatus.URFU_STUDENT,
        ParticipantStatus.UNIVERSITY_EMPLOYEE,
    }
)


class RegistrationStep(StrEnum):
    CAPTCHA = "captcha"
    CONSENT = "consent"
    STATUS = "status"
    INSTITUTE = "institute"
    TIMEZONE = "timezone"
    COMPLETE = "complete"


def is_registration_complete(user: User) -> bool:
    return (
        user.registered_at is not None
        and user.status is not None
        and user.timezone is not None
    )


def _has_persisted_progress(user: User) -> bool:
    return any(
        value is not None
        for value in (
            user.registered_at,
            user.status,
            user.institute,
            user.timezone,
        )
    )


def _captcha_passed(user: User, state_data: Mapping[str, Any]) -> bool:
    return bool(state_data.get(CAPTCHA_PASSED_KEY)) or _has_persisted_progress(user)


def _consent_accepted(user: User, state_data: Mapping[str, Any]) -> bool:
    return bool(state_data.get(CONSENT_ACCEPTED_KEY)) or user.registered_at is not None


def resolve_registration_step(
    user: User,
    state_data: Mapping[str, Any] | None = None,
) -> RegistrationStep:
    data = state_data or {}

    if is_registration_complete(user):
        return RegistrationStep.COMPLETE
    if not _captcha_passed(user, data):
        return RegistrationStep.CAPTCHA
    if not _consent_accepted(user, data):
        return RegistrationStep.CONSENT
    if user.status is None:
        return RegistrationStep.STATUS
    if user.status in INSTITUTE_REQUIRED_STATUSES and not user.institute:
        return RegistrationStep.INSTITUTE
    if user.timezone is None:
        return RegistrationStep.TIMEZONE
    return RegistrationStep.COMPLETE


async def resume_registration(
    state: FSMContext,
    user: User,
) -> RegistrationStep:
    """Resolve the next step and remember it for subsequent handlers."""
    data = await state.get_data()
    step = resolve_registration_step(user, data)
    if data.get(REGISTRATION_STEP_KEY) != step.value:
        await state.update_data({REGISTRATION_STEP_KEY: step.value})
    return step


__all__ = [
    "CAPTCHA_PASSED_KEY",
    "CONSENT_ACCEPTED_KEY",
    "INSTITUTE_REQUIRED_STATUSES",
    "REGISTRATION_STEP_KEY",
    "RegistrationStep",
    "is_registration_complete",
    "resolve_registration_step",
    "resume_registration",
]
