"""Captcha challenge generation and FSM state helpers (FLOWS 3)."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.content import texts
from app.keyboards import CAPTCHA_BUTTON_COUNT

CAPTCHA_CORRECT_KEY = "captcha_correct"
CAPTCHA_KIND_KEY = "captcha_kind"
CAPTCHA_OPTIONS_KEY = "captcha_options"
CAPTCHA_WRONG_ATTEMPTS_KEY = "captcha_wrong_attempts"

CAPTCHA_MAX_ATTEMPTS = 3
CAPTCHA_KINDS = (texts.CAPTCHA_KIND_EMOJI, texts.CAPTCHA_KIND_ICON)


@dataclass(frozen=True, slots=True)
class CaptchaChallenge:
    correct: str
    options: tuple[str, ...]
    kind: str

    def question(self) -> str:
        return texts.format_captcha_question(
            self.kind,
            texts.CAPTCHA_EMOJI_NAMES[self.correct],
        )

    def as_state(self) -> dict[str, Any]:
        return {
            CAPTCHA_CORRECT_KEY: self.correct,
            CAPTCHA_KIND_KEY: self.kind,
            CAPTCHA_OPTIONS_KEY: list(self.options),
        }


def create_captcha_challenge(
    rng: random.Random | None = None,
) -> CaptchaChallenge:
    source = rng or random
    correct = source.choice(texts.CAPTCHA_EMOJIS)
    others = [emoji for emoji in texts.CAPTCHA_EMOJIS if emoji != correct]
    options = [correct, *source.sample(others, CAPTCHA_BUTTON_COUNT - 1)]
    source.shuffle(options)
    kind = source.choice(CAPTCHA_KINDS)
    return CaptchaChallenge(
        correct=correct,
        options=tuple(options),
        kind=kind,
    )


def challenge_from_state(
    state_data: Mapping[str, Any],
) -> CaptchaChallenge | None:
    correct = state_data.get(CAPTCHA_CORRECT_KEY)
    kind = state_data.get(CAPTCHA_KIND_KEY)
    options = state_data.get(CAPTCHA_OPTIONS_KEY)

    if not isinstance(options, Sequence) or isinstance(options, str):
        return None
    normalized = tuple(options)
    if len(normalized) != CAPTCHA_BUTTON_COUNT:
        return None
    if len(set(normalized)) != len(normalized):
        return None
    if any(
        not isinstance(option, str)
        or option not in texts.CAPTCHA_EMOJI_NAMES
        for option in normalized
    ):
        return None
    if not isinstance(correct, str) or correct not in normalized:
        return None
    if kind not in CAPTCHA_KINDS:
        return None

    return CaptchaChallenge(
        correct=correct,
        options=normalized,
        kind=kind,
    )


def wrong_attempts_from_state(state_data: Mapping[str, Any]) -> int:
    value = state_data.get(CAPTCHA_WRONG_ATTEMPTS_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def captcha_attempts_left(wrong_attempts: int) -> int:
    return max(CAPTCHA_MAX_ATTEMPTS - wrong_attempts, 0)


__all__ = [
    "CAPTCHA_CORRECT_KEY",
    "CAPTCHA_KIND_KEY",
    "CAPTCHA_KINDS",
    "CAPTCHA_MAX_ATTEMPTS",
    "CAPTCHA_OPTIONS_KEY",
    "CAPTCHA_WRONG_ATTEMPTS_KEY",
    "CaptchaChallenge",
    "captcha_attempts_left",
    "challenge_from_state",
    "create_captcha_challenge",
    "wrong_attempts_from_state",
]
