from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content import texts
from app.db.enums import ParticipantStatus
from app.db.requests import (
    create_user,
    mark_user_registered,
    set_user_banned,
    set_user_status,
)
from app.handlers import start
from app.keyboards import (
    INSTITUTE_CALLBACK_PREFIX,
    STATUS_CALLBACK_PREFIX,
)
from app.services import (
    CAPTCHA_PASSED_KEY,
    CONSENT_ACCEPTED_KEY,
    INSTITUTE_REQUIRED_STATUSES,
    REGISTRATION_STEP_KEY,
    TEST_INSTITUTES,
    RegistrationStep,
    institute_options,
    parse_institute,
    parse_status,
    parse_timezone,
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


def make_config(*, institutes: tuple[str, ...] = ()) -> Config:
    return Config(bot_token="123456:fake", institutes=institutes)


def profile_state(step: RegistrationStep) -> dict[str, Any]:
    return {
        CAPTCHA_PASSED_KEY: True,
        CONSENT_ACCEPTED_KEY: True,
        REGISTRATION_STEP_KEY: step.value,
    }


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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5", 5),
        ("+5", 5),
        ("-3", -3),
        (" 05 ", 5),
        ("0", 0),
        ("14", 14),
        ("-12", -12),
    ],
)
def test_parse_timezone_accepts_integers(
    value: str,
    expected: int,
) -> None:
    assert parse_timezone(value) == expected


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "abc", "5.0", "5h", "--5", "15", "-13"],
)
def test_parse_timezone_rejects_invalid_values(value: str | None) -> None:
    assert parse_timezone(value) is None


def test_institute_options_prefers_configured_list() -> None:
    assert institute_options(("Институт 1", "Институт 2")) == (
        "Институт 1",
        "Институт 2",
    )


def test_institute_options_falls_back_to_test_list() -> None:
    assert institute_options(()) == TEST_INSTITUTES
    assert institute_options(None) == TEST_INSTITUTES
    assert TEST_INSTITUTES == ("ИРИТ-РТФ", "ИнЭУ", "ГУК")


def test_parse_status_accepts_known_values() -> None:
    assert parse_status("urfu_student") is ParticipantStatus.URFU_STUDENT
    assert parse_status("other") is ParticipantStatus.OTHER


def test_parse_status_rejects_unknown_values() -> None:
    assert parse_status("unknown") is None
    assert parse_status("") is None


def test_parse_institute_uses_index_and_bounds() -> None:
    institutes = ("ИРИТ-РТФ", "ИнЭУ", "ГУК")

    assert parse_institute("0", institutes) == "ИРИТ-РТФ"
    assert parse_institute("2", institutes) == "ГУК"
    assert parse_institute("3", institutes) is None
    assert parse_institute("-1", institutes) is None
    assert parse_institute("abc", institutes) is None


@pytest.mark.asyncio
async def test_start_at_status_sends_status_question(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(session, user)
    message = make_message(text="/start")

    await start.handle_start(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert args[0] == texts.STATUS_QUESTION
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [
            (
                texts.PARTICIPANT_STATUS_LABELS[status],
                f"{STATUS_CALLBACK_PREFIX}{status.value}",
            )
        ]
        for status in ParticipantStatus
    ]


@pytest.mark.asyncio
async def test_start_at_institute_sends_configured_institutes(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(session, user)
    await set_user_status(session, user, ParticipantStatus.URFU_STUDENT)
    message = make_message(text="/start")
    config = make_config(institutes=("Институт 1", "Институт 2"))

    await start.handle_start(
        message,
        state=FakeFSMContext(),
        session=session,
        config=config,
    )

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert args[0] == texts.INSTITUTE_QUESTION
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [("Институт 1", f"{INSTITUTE_CALLBACK_PREFIX}0")],
        [("Институт 2", f"{INSTITUTE_CALLBACK_PREFIX}1")],
    ]


@pytest.mark.asyncio
async def test_start_at_institute_uses_test_list_when_config_empty(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(session, user)
    await set_user_status(
        session,
        user,
        ParticipantStatus.UNIVERSITY_EMPLOYEE,
    )
    message = make_message(text="/start")

    await start.handle_start(
        message,
        state=FakeFSMContext(),
        session=session,
        config=make_config(),
    )

    args, kwargs = message.answer.await_args
    assert args[0] == texts.INSTITUTE_QUESTION
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [(institute, f"{INSTITUTE_CALLBACK_PREFIX}{index}")]
        for index, institute in enumerate(TEST_INSTITUTES)
    ]


@pytest.mark.asyncio
async def test_start_at_timezone_sends_timezone_question(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(session, user)
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    message = make_message(text="/start")

    await start.handle_start(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_awaited_once_with(texts.TIMEZONE_QUESTION)


@pytest.mark.asyncio
async def test_status_choice_for_urfu_student_moves_to_institute(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(profile_state(RegistrationStep.STATUS))
    callback = make_callback(
        data=f"{STATUS_CALLBACK_PREFIX}{ParticipantStatus.URFU_STUDENT.value}"
    )
    config = make_config(institutes=("Институт 1", "Институт 2"))

    await start.handle_status_choice(
        callback,
        state=state,
        session=session,
        config=config,
    )

    assert user.status is ParticipantStatus.URFU_STUDENT
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.INSTITUTE.value
    callback.answer.assert_awaited_once_with()
    args, kwargs = callback.message.edit_text.await_args
    assert args[0] == texts.INSTITUTE_QUESTION
    assert keyboard_rows(kwargs["reply_markup"]) == [
        [("Институт 1", f"{INSTITUTE_CALLBACK_PREFIX}0")],
        [("Институт 2", f"{INSTITUTE_CALLBACK_PREFIX}1")],
    ]


@pytest.mark.asyncio
async def test_status_choice_for_applicant_moves_to_timezone(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(profile_state(RegistrationStep.STATUS))
    callback = make_callback(
        data=f"{STATUS_CALLBACK_PREFIX}{ParticipantStatus.APPLICANT.value}"
    )

    await start.handle_status_choice(
        callback,
        state=state,
        session=session,
    )

    assert user.status is ParticipantStatus.APPLICANT
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.TIMEZONE.value
    callback.message.edit_text.assert_awaited_once_with(
        texts.TIMEZONE_QUESTION,
        reply_markup=None,
    )


@pytest.mark.asyncio
async def test_status_choice_rejects_unknown_status(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(profile_state(RegistrationStep.STATUS))
    callback = make_callback(data=f"{STATUS_CALLBACK_PREFIX}unknown")

    await start.handle_status_choice(
        callback,
        state=state,
        session=session,
    )

    assert user.status is None
    callback.answer.assert_not_awaited()
    callback.message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_status_choice_ignored_outside_status_step(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(profile_state(RegistrationStep.TIMEZONE))
    callback = make_callback(
        data=f"{STATUS_CALLBACK_PREFIX}{ParticipantStatus.APPLICANT.value}"
    )

    await start.handle_status_choice(
        callback,
        state=state,
        session=session,
    )

    assert user.status is None
    callback.answer.assert_not_awaited()
    callback.message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_institute_choice_saves_institute_and_moves_to_timezone(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(session, user, ParticipantStatus.URFU_STUDENT)
    state = FakeFSMContext(profile_state(RegistrationStep.INSTITUTE))
    callback = make_callback(data=f"{INSTITUTE_CALLBACK_PREFIX}1")
    config = make_config(institutes=("Институт 1", "Институт 2"))

    await start.handle_institute_choice(
        callback,
        state=state,
        session=session,
        config=config,
    )

    assert user.institute == "Институт 2"
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.TIMEZONE.value
    callback.answer.assert_awaited_once_with()
    callback.message.edit_text.assert_awaited_once_with(
        texts.TIMEZONE_QUESTION,
        reply_markup=None,
    )


@pytest.mark.asyncio
async def test_institute_choice_uses_test_list_when_config_empty(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(
        session,
        user,
        ParticipantStatus.UNIVERSITY_EMPLOYEE,
    )
    state = FakeFSMContext(profile_state(RegistrationStep.INSTITUTE))
    callback = make_callback(data=f"{INSTITUTE_CALLBACK_PREFIX}0")

    await start.handle_institute_choice(
        callback,
        state=state,
        session=session,
        config=make_config(),
    )

    assert user.institute == TEST_INSTITUTES[0]


@pytest.mark.asyncio
async def test_institute_choice_rejects_invalid_index(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(session, user, ParticipantStatus.URFU_STUDENT)
    state = FakeFSMContext(profile_state(RegistrationStep.INSTITUTE))
    callback = make_callback(data=f"{INSTITUTE_CALLBACK_PREFIX}99")

    await start.handle_institute_choice(
        callback,
        state=state,
        session=session,
    )

    assert user.institute is None
    callback.answer.assert_not_awaited()
    callback.message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_institute_choice_ignored_for_status_without_institute(
    session: AsyncSession,
    make_callback,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    state = FakeFSMContext(profile_state(RegistrationStep.INSTITUTE))
    callback = make_callback(data=f"{INSTITUTE_CALLBACK_PREFIX}0")

    await start.handle_institute_choice(
        callback,
        state=state,
        session=session,
    )

    assert user.institute is None
    callback.answer.assert_not_awaited()
    callback.message.edit_text.assert_not_awaited()


@pytest.mark.parametrize(
    ("text", "expected"),
    [("5", 5), ("+5", 5), ("-3", -3), (" 05 ", 5)],
)
@pytest.mark.asyncio
async def test_timezone_input_completes_registration(
    session: AsyncSession,
    make_message,
    text: str,
    expected: int,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    state = FakeFSMContext(profile_state(RegistrationStep.TIMEZONE))
    message = make_message(text=text)

    await start.handle_timezone_input(
        message,
        state=state,
        session=session,
    )

    assert user.timezone == expected
    assert user.registered_at is not None
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.COMPLETE.value
    assert message.answer.await_count == 2
    assert message.answer.await_args_list[0].args[0] == texts.REGISTRATION_DONE
    assert message.answer.await_args_list[1].args[0] == texts.CIRCLE_ASK


@pytest.mark.asyncio
async def test_timezone_input_rejects_invalid_value(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    state = FakeFSMContext(profile_state(RegistrationStep.TIMEZONE))
    message = make_message(text="abc")

    await start.handle_timezone_input(
        message,
        state=state,
        session=session,
    )

    assert user.timezone is None
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.TIMEZONE.value
    message.answer.assert_awaited_once_with(texts.TIMEZONE_INVALID)


@pytest.mark.asyncio
async def test_timezone_input_ignored_outside_timezone_step(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    state = FakeFSMContext(profile_state(RegistrationStep.STATUS))
    message = make_message(text="5")

    await start.handle_timezone_input(
        message,
        state=state,
        session=session,
    )

    assert user.timezone is None
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_timezone_input_ignores_banned_participant(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    await set_user_banned(session, user)
    state = FakeFSMContext(profile_state(RegistrationStep.TIMEZONE))
    message = make_message(text="5")

    await start.handle_timezone_input(
        message,
        state=state,
        session=session,
    )

    assert user.timezone is None
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_timezone_input_ignores_user_without_status(
    session: AsyncSession,
    make_message,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    state = FakeFSMContext(profile_state(RegistrationStep.TIMEZONE))
    message = make_message(text="5")

    await start.handle_timezone_input(
        message,
        state=state,
        session=session,
    )

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_timezone_input_ignores_missing_required_institute(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await set_user_status(session, user, ParticipantStatus.URFU_STUDENT)
    state = FakeFSMContext(profile_state(RegistrationStep.TIMEZONE))
    message = make_message(text="5")

    await start.handle_timezone_input(
        message,
        state=state,
        session=session,
    )

    assert user.timezone is None
    message.answer.assert_not_awaited()


def test_institute_required_statuses_are_urfu_only() -> None:
    assert INSTITUTE_REQUIRED_STATUSES == {
        ParticipantStatus.URFU_STUDENT,
        ParticipantStatus.UNIVERSITY_EMPLOYEE,
    }
