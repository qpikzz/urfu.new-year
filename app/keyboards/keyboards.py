"""Inline keyboards built from the texts in MESSAGES."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.content import texts
from app.db.enums import ParticipantStatus, RejectionReason

CAPTCHA_CALLBACK_PREFIX = "captcha:"
CONSENT_ACCEPT_CALLBACK = "consent:accept"
STATUS_CALLBACK_PREFIX = "status:"
INSTITUTE_CALLBACK_PREFIX = "institute:"
MODERATION_APPROVE_CALLBACK = "moderation:approve"
MODERATION_CANCEL_CALLBACK = "moderation:cancel"
MODERATION_REJECT_CALLBACK = "moderation:reject"
MODERATION_REJECT_CALLBACK_PREFIX = f"{MODERATION_REJECT_CALLBACK}:"

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


def rejection_callback_data(reason: RejectionReason) -> str:
    return f"{MODERATION_REJECT_CALLBACK_PREFIX}{reason.value}"


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


def moderation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    texts.MODERATION_APPROVE_BUTTON,
                    MODERATION_APPROVE_CALLBACK,
                ),
                _button(
                    texts.MODERATION_REJECT_BUTTON,
                    MODERATION_REJECT_CALLBACK,
                ),
            ]
        ]
    )


def rejection_reasons_keyboard() -> InlineKeyboardMarkup:
    return _single_column(
        [
            (texts.REJECTION_CANCEL_BUTTON, MODERATION_CANCEL_CALLBACK),
            (
                texts.REJECTION_PROFANITY_BUTTON,
                rejection_callback_data(RejectionReason.PROFANITY),
            ),
            (
                texts.REJECTION_SHOCKING_CONTENT_BUTTON,
                rejection_callback_data(RejectionReason.SHOCKING_CONTENT),
            ),
            (
                texts.REJECTION_ADVERTISING_BUTTON,
                rejection_callback_data(RejectionReason.ADVERTISING),
            ),
            (
                texts.REJECTION_OTHER_BUTTON,
                rejection_callback_data(RejectionReason.OTHER),
            ),
        ]
    )
