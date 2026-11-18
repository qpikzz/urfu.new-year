from __future__ import annotations

import pytest
from aiogram.types import InlineKeyboardMarkup

from app.content import texts
from app.db.enums import ParticipantStatus, RejectionReason
from app.keyboards import (
    CAPTCHA_CALLBACK_PREFIX,
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_CONTINUE_CALLBACK,
    captcha_keyboard,
    consent_continue_keyboard,
    consent_keyboard,
    institutes_keyboard,
    moderation_approve_callback_data,
    moderation_cancel_callback_data,
    moderation_keyboard,
    moderation_reject_callback_data,
    rejection_callback_data,
    rejection_reasons_keyboard,
    status_keyboard,
)

CIR_ID = 42


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
    rows = _rows(moderation_keyboard(CIR_ID))

    assert rows == [
        [
            (
                texts.MODERATION_APPROVE_BUTTON,
                moderation_approve_callback_data(CIR_ID),
            ),
            (
                texts.MODERATION_REJECT_BUTTON,
                moderation_reject_callback_data(CIR_ID),
            ),
        ]
    ]


def test_rejection_reasons_keyboard_has_all_options_in_order() -> None:
    rows = _rows(rejection_reasons_keyboard(CIR_ID))

    assert rows == [
        [
            (
                texts.REJECTION_CANCEL_BUTTON,
                moderation_cancel_callback_data(CIR_ID),
            )
        ],
        [
            (
                texts.REJECTION_PROFANITY_BUTTON,
                rejection_callback_data(CIR_ID, RejectionReason.PROFANITY),
            )
        ],
        [
            (
                texts.REJECTION_SHOCKING_CONTENT_BUTTON,
                rejection_callback_data(
                    CIR_ID,
                    RejectionReason.SHOCKING_CONTENT,
                ),
            )
        ],
        [
            (
                texts.REJECTION_ADVERTISING_BUTTON,
                rejection_callback_data(CIR_ID, RejectionReason.ADVERTISING),
            )
        ],
        [
            (
                texts.REJECTION_OTHER_BUTTON,
                rejection_callback_data(CIR_ID, RejectionReason.OTHER),
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
        moderation_keyboard(CIR_ID),
        rejection_reasons_keyboard(CIR_ID),
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
