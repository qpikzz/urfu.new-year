from __future__ import annotations

import random
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import texts
from app.content.texts import (
    CAPTCHA_FAILED,
    CAPTCHA_PASSED,
    START_WELCOME,
    format_captcha_wrong,
)
from app.db.requests import create_user, set_user_banned
from app.handlers import start
from app.keyboards import (
    CAPTCHA_CALLBACK_PREFIX,
    CONSENT_CONTINUE_CALLBACK,
)
from app.services import (
    CAPTCHA_CORRECT_KEY,
    CAPTCHA_KINDS,
    CAPTCHA_MAX_ATTEMPTS,
    CAPTCHA_OPTIONS_KEY,
    CAPTCHA_PASSED_KEY,
    CAPTCHA_WRONG_ATTEMPTS_KEY,
    REGISTRATION_STEP_KEY,
    CaptchaChallenge,
    RegistrationStep,
    captcha_attempts_left,
    challenge_from_state,
    create_captcha_challenge,
    wrong_attempts_from_state,
)

DEFAULT_CHALLENGE = CaptchaChallenge(
    correct="❤️",
    options=("❤️", "⚡", "🦴", "👁"),
    kind=texts.CAPTCHA_KIND_EMOJI,
)
NEW_CHALLENGE = CaptchaChallenge(
    correct="🍎",
    options=("🍎", "🍉", "🧊", "⭐"),
    kind=texts.CAPTCHA_KIND_ICON,
)


class FakeFSMContext:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = dict(data or {})

    async def get_data(self) -> dict[str, Any]:
        return dict(self.data)

    async def update_data(
        self,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        values = dict(data or {})
        values.update(kwargs)
        self.data.update(values)

    async def clear(self) -> None:
        self.data.clear()


def captcha_state(
    challenge: CaptchaChallenge = DEFAULT_CHALLENGE,
    *,
    attempts: int = 0,
) -> dict[str, Any]:
    data = challenge.as_state()
    data[REGISTRATION_STEP_KEY] = RegistrationStep.CAPTCHA.value
    data[CAPTCHA_WRONG_ATTEMPTS_KEY] = attempts
    return data


def keyboard_rows(reply_markup) -> list[list[tuple[str, str]]]:
    return [
        [(button.text, button.callback_data) for button in row]
        for row in reply_markup.inline_keyboard
    ]


@pytest.fixture(autouse=True)
def fake_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        start,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


@pytest.mark.parametrize("seed", range(20))
def test_generated_challenge_uses_valid_emoji(seed: int) -> None:
    challenge = create_captcha_challenge(random.Random(seed))

    assert challenge.correct in texts.CAPTCHA_EMOJI_NAMES
    assert len(challenge.options) == 4
    assert len(set(challenge.options)) == 4
    assert challenge.correct in challenge.options
    assert set(challenge.options) <= set(texts.CAPTCHA_EMOJI_NAMES)
    assert challenge.kind in CAPTCHA_KINDS


def test_challenge_question_uses_emoji_name_and_kind() -> None:
    assert DEFAULT_CHALLENGE.question() == "🔎 Нажми на эмодзи: «Сердце»"
    assert NEW_CHALLENGE.question() == "🔎 Нажми на иконку: «Яблоко»"


def test_challenge_state_round_trip() -> None:
    restored = challenge_from_state(DEFAULT_CHALLENGE.as_state())

    assert restored == DEFAULT_CHALLENGE


@pytest.mark.parametrize(
    "data",
    [
        {},
        {
            CAPTCHA_CORRECT_KEY: "❤️",
            "captcha_kind": texts.CAPTCHA_KIND_EMOJI,
            CAPTCHA_OPTIONS_KEY: ["❤️", "⚡", "🦴"],
        },
        {
            CAPTCHA_CORRECT_KEY: "❤️",
            "captcha_kind": texts.CAPTCHA_KIND_EMOJI,
            CAPTCHA_OPTIONS_KEY: ["❤️", "⚡", "🦴", "🦴"],
        },
        {
            CAPTCHA_CORRECT_KEY: "❤️",
            "captcha_kind": texts.CAPTCHA_KIND_EMOJI,
            CAPTCHA_OPTIONS_KEY: ["❤️", "⚡", "🦴", "X"],
        },
        {
            CAPTCHA_CORRECT_KEY: "🍎",
            "captcha_kind": texts.CAPTCHA_KIND_EMOJI,
            CAPTCHA_OPTIONS_KEY: ["❤️", "⚡", "🦴", "👁"],
        },
        {
            CAPTCHA_CORRECT_KEY: "❤️",
            "captcha_kind": "unknown",
            CAPTCHA_OPTIONS_KEY: ["❤️", "⚡", "🦴", "👁"],
        },
        {
            CAPTCHA_CORRECT_KEY: "❤️",
            "captcha_kind": texts.CAPTCHA_KIND_EMOJI,
            CAPTCHA_OPTIONS_KEY: "❤️⚡🦴👁",
        },
    ],
)
def test_challenge_from_state_rejects_invalid_data(
    data: dict[str, Any],
) -> None:
    assert challenge_from_state(data) is None


def test_wrong_attempts_defaults_and_validation() -> None:
    assert wrong_attempts_from_state({}) == 0
    assert wrong_attempts_from_state({CAPTCHA_WRONG_ATTEMPTS_KEY: 2}) == 2
    assert wrong_attempts_from_state({CAPTCHA_WRONG_ATTEMPTS_KEY: -1}) == 0
    assert wrong_attempts_from_state({CAPTCHA_WRONG_ATTEMPTS_KEY: "2"}) == 0
    assert wrong_attempts_from_state({CAPTCHA_WRONG_ATTEMPTS_KEY: True}) == 0


def test_attempts_left_never_goes_negative() -> None:
    assert captcha_attempts_left(0) == CAPTCHA_MAX_ATTEMPTS
    assert captcha_attempts_left(2) == 1
    assert captcha_attempts_left(3) == 0
    assert captcha_attempts_left(4) == 0


@pytest.mark.asyncio
async def test_start_sends_welcome_and_captcha_to_new_user(
    session: AsyncSession,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        start,
        "create_captcha_challenge",
        lambda: DEFAULT_CHALLENGE,
    )
    message = make_message(text="/start")
    state = FakeFSMContext()

    await start.handle_start(message, state=state, session=session)

    assert message.answer.await_count == 2
    assert message.answer.await_args_list[0].args[0] == START_WELCOME
    question_call = message.answer.await_args_list[1]
    assert question_call.args[0] == DEFAULT_CHALLENGE.question()
    assert keyboard_rows(question_call.kwargs["reply_markup"]) == [
        [
            (emoji, f"{CAPTCHA_CALLBACK_PREFIX}{emoji}")
            for emoji in DEFAULT_CHALLENGE.options
        ]
    ]
    assert state.data[CAPTCHA_CORRECT_KEY] == DEFAULT_CHALLENGE.correct
    assert state.data[CAPTCHA_OPTIONS_KEY] == list(DEFAULT_CHALLENGE.options)
    assert state.data[CAPTCHA_WRONG_ATTEMPTS_KEY] == 0


@pytest.mark.asyncio
async def test_start_resumes_captcha_without_welcome_or_reset(
    session: AsyncSession,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(captcha_state(attempts=1))

    def fail() -> CaptchaChallenge:
        pytest.fail("a valid active challenge must be reused")

    monkeypatch.setattr(start, "create_captcha_challenge", fail)
    message = make_message(text="/start")

    await start.handle_start(message, state=state, session=session)

    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == DEFAULT_CHALLENGE.question()
    assert state.data[CAPTCHA_CORRECT_KEY] == DEFAULT_CHALLENGE.correct
    assert state.data[CAPTCHA_WRONG_ATTEMPTS_KEY] == 1


@pytest.mark.asyncio
async def test_correct_answer_passes_captcha(
    session: AsyncSession,
    make_callback,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(captcha_state())
    callback = make_callback(
        data=f"{CAPTCHA_CALLBACK_PREFIX}{DEFAULT_CHALLENGE.correct}"
    )

    await start.handle_captcha_answer(
        callback,
        state=state,
        session=session,
    )

    assert state.data[CAPTCHA_PASSED_KEY] is True
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.CONSENT.value
    assert state.data[CAPTCHA_WRONG_ATTEMPTS_KEY] == 0
    callback.answer.assert_awaited_once_with()
    args, kwargs = callback.message.edit_text.await_args
    assert args[0] == CAPTCHA_PASSED
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [(texts.CONSENT_CONTINUE_BUTTON, CONSENT_CONTINUE_CALLBACK)]
    ]


@pytest.mark.asyncio
async def test_wrong_answer_shows_attempts_and_new_captcha(
    session: AsyncSession,
    make_callback,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(captcha_state())
    callback = make_callback(data=f"{CAPTCHA_CALLBACK_PREFIX}⚡")
    monkeypatch.setattr(
        start,
        "create_captcha_challenge",
        lambda: NEW_CHALLENGE,
    )

    await start.handle_captcha_answer(
        callback,
        state=state,
        session=session,
    )

    callback.answer.assert_awaited_once_with(format_captcha_wrong(2))
    args, kwargs = callback.message.edit_text.await_args
    assert args[0] == NEW_CHALLENGE.question()
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [
            (emoji, f"{CAPTCHA_CALLBACK_PREFIX}{emoji}")
            for emoji in NEW_CHALLENGE.options
        ]
    ]
    assert state.data[CAPTCHA_CORRECT_KEY] == NEW_CHALLENGE.correct
    assert state.data[CAPTCHA_WRONG_ATTEMPTS_KEY] == 1
    assert state.data.get(CAPTCHA_PASSED_KEY) is None


@pytest.mark.asyncio
async def test_second_wrong_answer_reports_one_attempt_left(
    session: AsyncSession,
    make_callback,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(captcha_state(attempts=1))
    callback = make_callback(data=f"{CAPTCHA_CALLBACK_PREFIX}⚡")
    monkeypatch.setattr(
        start,
        "create_captcha_challenge",
        lambda: NEW_CHALLENGE,
    )

    await start.handle_captcha_answer(
        callback,
        state=state,
        session=session,
    )

    callback.answer.assert_awaited_once_with(format_captcha_wrong(1))
    assert state.data[CAPTCHA_WRONG_ATTEMPTS_KEY] == 2


@pytest.mark.asyncio
async def test_third_wrong_answer_bans_participant(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(captcha_state(attempts=2))
    callback = make_callback(data=f"{CAPTCHA_CALLBACK_PREFIX}⚡")

    await start.handle_captcha_answer(
        callback,
        state=state,
        session=session,
    )

    assert user.is_banned
    assert state.data == {}
    callback.answer.assert_awaited_once_with()
    callback.message.edit_text.assert_awaited_once_with(
        CAPTCHA_FAILED,
        reply_markup=None,
    )


@pytest.mark.asyncio
async def test_captcha_ignores_banned_participant(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_banned(session, user)
    state = FakeFSMContext(captcha_state())
    callback = make_callback(
        data=f"{CAPTCHA_CALLBACK_PREFIX}{DEFAULT_CHALLENGE.correct}"
    )

    await start.handle_captcha_answer(
        callback,
        state=state,
        session=session,
    )

    callback.answer.assert_not_awaited()
    callback.message.edit_text.assert_not_awaited()
    assert state.data.get(CAPTCHA_PASSED_KEY) is None


@pytest.mark.asyncio
async def test_captcha_ignores_callback_outside_captcha_step(
    session: AsyncSession,
    make_callback,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    data = captcha_state()
    data[REGISTRATION_STEP_KEY] = RegistrationStep.CONSENT.value
    state = FakeFSMContext(data)
    callback = make_callback(
        data=f"{CAPTCHA_CALLBACK_PREFIX}{DEFAULT_CHALLENGE.correct}"
    )

    await start.handle_captcha_answer(
        callback,
        state=state,
        session=session,
    )

    callback.answer.assert_not_awaited()
    callback.message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_captcha_ignores_callback_without_active_challenge(
    session: AsyncSession,
    make_callback,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(
        {REGISTRATION_STEP_KEY: RegistrationStep.CAPTCHA.value}
    )
    callback = make_callback(
        data=f"{CAPTCHA_CALLBACK_PREFIX}{DEFAULT_CHALLENGE.correct}"
    )

    await start.handle_captcha_answer(
        callback,
        state=state,
        session=session,
    )

    callback.answer.assert_not_awaited()
    callback.message.edit_text.assert_not_awaited()
