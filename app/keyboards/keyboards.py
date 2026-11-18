"""Inline keyboards built from the texts in MESSAGES."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.content import texts
from app.db.enums import ParticipantStatus, RejectionReason

CAPTCHA_CALLBACK_PREFIX = "captcha:"
CONSENT_CONTINUE_CALLBACK = "consent:continue"
CONSENT_ACCEPT_CALLBACK = "consent:accept"
STATUS_CALLBACK_PREFIX = "status:"
INSTITUTE_CALLBACK_PREFIX = "institute:"
MODERATION_CALLBACK_PREFIX = "moderation:"
MODERATION_APPROVE_ACTION = "approve"
MODERATION_REJECT_ACTION = "reject"
MODERATION_CANCEL_ACTION = "cancel"

CAPTCHA_BUTTON_COUNT = 4


def _button(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _single_column(rows: Sequence[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button(text, callback_data)] for text, callback_data in rows]
    )


def status_callback_data(status: ParticipantStatus) -> str:
    return f"{STATUS_CALLBACK_PREFIX}{status.value}"


def institute_callback_data(index: int) -> str:
    return f"{INSTITUTE_CALLBACK_PREFIX}{index}"


def moderation_approve_callback_data(cir_id: int) -> str:
    return (
        f"{MODERATION_CALLBACK_PREFIX}{MODERATION_APPROVE_ACTION}:{cir_id}"
    )


def moderation_reject_callback_data(cir_id: int) -> str:
    return f"{MODERATION_CALLBACK_PREFIX}{MODERATION_REJECT_ACTION}:{cir_id}"


def moderation_cancel_callback_data(cir_id: int) -> str:
    return f"{MODERATION_CALLBACK_PREFIX}{MODERATION_CANCEL_ACTION}:{cir_id}"


def rejection_callback_data(cir_id: int, reason: RejectionReason) -> str:
    return (
        f"{MODERATION_CALLBACK_PREFIX}{MODERATION_REJECT_ACTION}"
        f":{cir_id}:{reason.value}"
    )


def captcha_keyboard(emojis: Sequence[str]) -> InlineKeyboardMarkup:
    options = tuple(emojis)
    if len(options) != CAPTCHA_BUTTON_COUNT:
        raise ValueError(
            f"captcha requires exactly {CAPTCHA_BUTTON_COUNT} options"
        )
    if len(set(options)) != len(options):
        raise ValueError("captcha options must be unique")
    if set(options) - set(texts.CAPTCHA_EMOJI_NAMES):
        raise ValueError("captcha options must come from the emoji set")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(emoji, f"{CAPTCHA_CALLBACK_PREFIX}{emoji}")
                for emoji in options
            ]
        ]
    )


def consent_continue_keyboard() -> InlineKeyboardMarkup:
    return _single_column(
        [(texts.CONSENT_CONTINUE_BUTTON, CONSENT_CONTINUE_CALLBACK)]
    )


def consent_keyboard() -> InlineKeyboardMarkup:
    return _single_column(
        [(texts.CONSENT_BUTTON, CONSENT_ACCEPT_CALLBACK)]
    )


def status_keyboard() -> InlineKeyboardMarkup:
    return _single_column(
        [
            (
                texts.PARTICIPANT_STATUS_LABELS[status],
                status_callback_data(status),
            )
            for status in ParticipantStatus
        ]
    )


def institutes_keyboard(institutes: Sequence[str]) -> InlineKeyboardMarkup:
    return _single_column(
        [
            (institute, institute_callback_data(index))
            for index, institute in enumerate(institutes)
        ]
    )


def moderation_keyboard(cir_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    texts.MODERATION_APPROVE_BUTTON,
                    moderation_approve_callback_data(cir_id),
                ),
                _button(
                    texts.MODERATION_REJECT_BUTTON,
                    moderation_reject_callback_data(cir_id),
                ),
            ]
        ]
    )


def rejection_reasons_keyboard(cir_id: int) -> InlineKeyboardMarkup:
    return _single_column(
        [
            (
                texts.REJECTION_CANCEL_BUTTON,
                moderation_cancel_callback_data(cir_id),
            ),
            (
                texts.REJECTION_PROFANITY_BUTTON,
                rejection_callback_data(cir_id, RejectionReason.PROFANITY),
            ),
            (
                texts.REJECTION_SHOCKING_CONTENT_BUTTON,
                rejection_callback_data(
                    cir_id,
                    RejectionReason.SHOCKING_CONTENT,
                ),
            ),
            (
                texts.REJECTION_ADVERTISING_BUTTON,
                rejection_callback_data(cir_id, RejectionReason.ADVERTISING),
            ),
            (
                texts.REJECTION_OTHER_BUTTON,
                rejection_callback_data(cir_id, RejectionReason.OTHER),
            ),
        ]
    )
