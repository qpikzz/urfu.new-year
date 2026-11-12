from __future__ import annotations

import pytest
from aiogram.types import InlineKeyboardMarkup

from app.content import texts
from app.db.enums import ParticipantStatus, RejectionReason
from app.keyboards import (
    CAPTCHA_CALLBACK_PREFIX,
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_CONTINUE_CALLBACK,
    MODERATION_APPROVE_CALLBACK,
    MODERATION_CANCEL_CALLBACK,
    MODERATION_REJECT_CALLBACK,
    captcha_keyboard,
    consent_continue_keyboard,
    consent_keyboard,
    institutes_keyboard,
    moderation_keyboard,
    rejection_reasons_keyboard,
    status_keyboard,
)


def _rows(
    keyboard: InlineKeyboardMarkup,
) -> list[list[tuple[str, str | None]]]:
    return [
        [(button.text, button.callback_data) for button in row]
        for row in keyboard.inline_keyboard
    ]


def test_captcha_keyboard_uses_four_emoji_buttons() -> None:
    emojis = ["❤️", "⚡", "🦴", "👁"]

    rows = _rows(captcha_keyboard(emojis))

    assert rows == [
        [(emoji, f"{CAPTCHA_CALLBACK_PREFIX}{emoji}") for emoji in emojis]
    ]


@pytest.mark.parametrize(
    "emojis",
    [
        ["❤️", "⚡", "🦴"],
        ["❤️", "⚡", "🦴", "👁", "🦷"],
        ["❤️", "❤️", "🦴", "👁"],
        ["❤️", "⚡", "🦴", "X"],
    ],
)
def test_captcha_keyboard_rejects_invalid_options(emojis) -> None:
    with pytest.raises(ValueError):
        captcha_keyboard(emojis)


def test_consent_continue_keyboard_has_continue_button() -> None:
    rows = _rows(consent_continue_keyboard())

    assert rows == [
        [(texts.CONSENT_CONTINUE_BUTTON, CONSENT_CONTINUE_CALLBACK)]
    ]


def test_consent_keyboard_has_accept_button() -> None:
    rows = _rows(consent_keyboard())

    assert rows == [[(texts.CONSENT_BUTTON, CONSENT_ACCEPT_CALLBACK)]]


def test_status_keyboard_has_every_status() -> None:
    rows = _rows(status_keyboard())

    assert rows == [
        [
            (
                texts.PARTICIPANT_STATUS_LABELS[status],
                f"status:{status.value}",
            )
        ]
        for status in ParticipantStatus
    ]


def test_institutes_keyboard_uses_supplied_list() -> None:
    institutes = ["ИРИТ-РТФ", "ИнЭУ", "ГУК"]

    rows = _rows(institutes_keyboard(institutes))

    assert rows == [
        [(institute, f"institute:{index}")]
        for index, institute in enumerate(institutes)
    ]


def test_institutes_keyboard_can_be_empty() -> None:
    assert institutes_keyboard([]).inline_keyboard == []


def test_moderation_keyboard_has_approve_and_reject_buttons() -> None:
    rows = _rows(moderation_keyboard())

    assert rows == [
        [
            (texts.MODERATION_APPROVE_BUTTON, MODERATION_APPROVE_CALLBACK),
            (texts.MODERATION_REJECT_BUTTON, MODERATION_REJECT_CALLBACK),
        ]
    ]


def test_rejection_reasons_keyboard_has_all_options_in_order() -> None:
    rows = _rows(rejection_reasons_keyboard())

    assert rows == [
        [(texts.REJECTION_CANCEL_BUTTON, MODERATION_CANCEL_CALLBACK)],
        [
            (
                texts.REJECTION_PROFANITY_BUTTON,
                f"moderation:reject:{RejectionReason.PROFANITY.value}",
            )
        ],
        [
            (
                texts.REJECTION_SHOCKING_CONTENT_BUTTON,
                f"moderation:reject:{RejectionReason.SHOCKING_CONTENT.value}",
            )
        ],
        [
            (
                texts.REJECTION_ADVERTISING_BUTTON,
                f"moderation:reject:{RejectionReason.ADVERTISING.value}",
            )
        ],
        [
            (
                texts.REJECTION_OTHER_BUTTON,
                f"moderation:reject:{RejectionReason.OTHER.value}",
            )
        ],
    ]


@pytest.mark.parametrize(
    "keyboard",
    [
        captcha_keyboard(["❤️", "⚡", "🦴", "👁"]),
        consent_continue_keyboard(),
        consent_keyboard(),
        status_keyboard(),
        institutes_keyboard(["ИРИТ-РТФ", "ИнЭУ", "ГУК"]),
        moderation_keyboard(),
        rejection_reasons_keyboard(),
    ],
)
def test_callback_data_fits_telegram_limit(
    keyboard: InlineKeyboardMarkup,
) -> None:
    callback_values = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]

    assert callback_values
    assert all(len(value.encode("utf-8")) <= 64 for value in callback_values)
