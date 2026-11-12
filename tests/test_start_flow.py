from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import create_dispatcher, run_bot
from app.config import Config, ConfigError
from app.content import texts
from app.db.enums import CircleStatus, ParticipantStatus, RejectionReason
from app.db.models import User
from app.db.requests import (
    create_circle,
    create_user,
    get_user,
    mark_user_registered,
    set_user_banned,
    set_user_circle,
    set_user_institute,
    set_user_status,
    set_user_timezone,
)
from app.handlers import start
from app.hid import HIDError
from app.middlewares import DatabaseMiddleware
from app.services import (
    CAPTCHA_PASSED_KEY,
    CONSENT_ACCEPTED_KEY,
    REGISTRATION_STEP_KEY,
    RegistrationStep,
    build_menu_text,
    is_registration_complete,
    resolve_registration_step,
    resume_registration,
)


class FakeFSMContext:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = dict(data or {})
        self.updated: list[dict[str, Any]] = []

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
        self.updated.append(values)

    async def clear(self) -> None:
        self.data.clear()


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.closed = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


def make_user(
    *,
    status: ParticipantStatus | None = None,
    institute: str | None = None,
    timezone: int | None = None,
    registered_at: datetime | None = None,
) -> User:
    return User(
        hid="hid-1",
        full_name="Test User",
        status=status,
        institute=institute,
        timezone=timezone,
        registered_at=registered_at,
    )


async def make_registered_user(
    session: AsyncSession,
    *,
    hid: str = "hid-1001",
    status: ParticipantStatus = ParticipantStatus.APPLICANT,
    institute: str | None = None,
    timezone: int = 5,
) -> User:
    user = await create_user(session, hid=hid, full_name="Test User")
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await set_user_status(session, user, status)
    if institute is not None:
        await set_user_institute(session, user, institute)
    await set_user_timezone(session, user, timezone)
    return user


@pytest.fixture(autouse=True)
def fake_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        start,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )


def test_new_user_starts_with_captcha() -> None:
    assert (
        resolve_registration_step(make_user())
        == RegistrationStep.CAPTCHA
    )


def test_passed_captcha_moves_to_consent() -> None:
    user = make_user()

    assert (
        resolve_registration_step(user, {CAPTCHA_PASSED_KEY: True})
        == RegistrationStep.CONSENT
    )


def test_accepted_consent_moves_to_status() -> None:
    user = make_user()

    step = resolve_registration_step(
        user,
        {CAPTCHA_PASSED_KEY: True, CONSENT_ACCEPTED_KEY: True},
    )

    assert step == RegistrationStep.STATUS


def test_urfu_student_is_asked_for_institute() -> None:
    user = make_user(
        status=ParticipantStatus.URFU_STUDENT,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert resolve_registration_step(user) == RegistrationStep.INSTITUTE


def test_university_employee_is_asked_for_institute() -> None:
    user = make_user(
        status=ParticipantStatus.UNIVERSITY_EMPLOYEE,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert resolve_registration_step(user) == RegistrationStep.INSTITUTE


def test_other_status_skips_institute() -> None:
    user = make_user(
        status=ParticipantStatus.OTHER,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert resolve_registration_step(user) == RegistrationStep.TIMEZONE


def test_timezone_completes_registration() -> None:
    user = make_user(
        status=ParticipantStatus.APPLICANT,
        timezone=5,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert is_registration_complete(user)
    assert resolve_registration_step(user) == RegistrationStep.COMPLETE


def test_profile_without_registered_at_returns_to_consent() -> None:
    user = make_user(
        status=ParticipantStatus.APPLICANT,
        timezone=5,
    )

    assert not is_registration_complete(user)
    assert resolve_registration_step(user) == RegistrationStep.CONSENT


@pytest.mark.asyncio
async def test_resume_registration_remembers_step() -> None:
    state = FakeFSMContext()
    user = make_user(
        status=ParticipantStatus.APPLICANT,
        timezone=5,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    step = await resume_registration(state, user)

    assert step == RegistrationStep.COMPLETE
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.COMPLETE.value


def test_menu_requires_completed_registration() -> None:
    with pytest.raises(ValueError):
        build_menu_text(make_user())


def test_menu_without_circle_uses_single_line() -> None:
    user = make_user(
        status=ParticipantStatus.APPLICANT,
        timezone=5,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    text = build_menu_text(user)

    assert text.startswith("⭐ Профиль")
    assert "👤 Статус: Абитуриент (школьник)" in text
    assert "🌐 Часовой пояс: UTC+5" in text
    assert "🎥 Кружок: не отправлен" in text


def test_menu_shows_institute_only_when_present() -> None:
    user = make_user(
        status=ParticipantStatus.URFU_STUDENT,
        institute="ИРИТ-РТФ",
        timezone=5,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    text = build_menu_text(user)

    assert "🏛 Институт: ИРИТ-РТФ" in text


def test_menu_shows_circle_and_rejection_reason() -> None:
    user = make_user(
        status=ParticipantStatus.APPLICANT,
        timezone=5,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    circle = create_circle_model(
        status=CircleStatus.REJECTED,
        rejection_reason=RejectionReason.OTHER,
    )

    text = build_menu_text(user, circle)

    assert "🆔 ID: 7" in text
    assert "📍 Статус: Отклонён" in text
    assert "⏱ Длительность: 10 с" in text
    assert "❗ Причина отказа: иная причина" in text


def test_menu_shows_buffered_approved_label() -> None:
    user = make_user(
        status=ParticipantStatus.APPLICANT,
        timezone=5,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    circle = create_circle_model(status=CircleStatus.APPROVED, is_buffered=True)

    text = build_menu_text(user, circle)

    assert texts.BUFFERED_CIRCLE_STATUS_LABEL in text


def create_circle_model(
    *,
    status: CircleStatus,
    rejection_reason: RejectionReason | None = None,
    is_buffered: bool = False,
) -> object:
    from app.db.models import Circle

    return Circle(
        id=7,
        owner_hid="hid-1",
        file_id="file-id",
        sent_at=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
        duration=10,
        status=status,
        rejection_reason=rejection_reason,
        is_buffered=is_buffered,
    )


@pytest.mark.asyncio
async def test_start_creates_user_and_sends_welcome(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/start")
    state = FakeFSMContext()

    await start.handle_start(message, state=state, session=session)

    user = await get_user(session, "hid-1001")
    assert user is not None
    assert user.full_name == "Test User"
    assert user.username == "test_user"
    assert message.answer.await_count == 2
    assert message.answer.await_args_list[0].args[0] == texts.START_WELCOME
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.CAPTCHA.value


@pytest.mark.asyncio
async def test_start_uses_zero_username_when_absent(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/start")
    message.from_user.username = None

    await start.handle_start(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    user = await get_user(session, "hid-1001")
    assert user is not None
    assert user.username == "0"


@pytest.mark.asyncio
async def test_start_resumes_interrupted_registration(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(
        session,
        hid="hid-1001",
        full_name="Old Name",
        username="old_username",
    )
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    message = make_message(text="/start")
    state = FakeFSMContext()

    await start.handle_start(message, state=state, session=session)

    assert user.full_name == "Test User"
    assert user.username == "test_user"
    message.answer.assert_not_awaited()
    assert state.data[REGISTRATION_STEP_KEY] == RegistrationStep.STATUS.value


@pytest.mark.asyncio
async def test_start_replies_with_menu_when_registration_is_complete(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    message = make_message(text="/start")
    state = FakeFSMContext()

    await start.handle_start(message, state=state, session=session)

    expected = build_menu_text(user)
    message.answer.assert_awaited_once_with(expected)
    assert state.data == {}


@pytest.mark.asyncio
async def test_start_menu_includes_latest_circle(
    session: AsyncSession,
    make_message,
) -> None:
    user = await make_registered_user(session)
    circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="file-id",
        duration=10,
        sent_at=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
        status=CircleStatus.APPROVED,
    )
    await set_user_circle(session, user, circle.id)
    message = make_message(text="/start")

    await start.handle_start(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    text = message.answer.await_args.args[0]
    assert "🆔 ID:" in text
    assert "📍 Статус: Одобрен" in text
    assert "⏱ Длительность: 10 с" in text


@pytest.mark.asyncio
async def test_start_ignores_banned_participant(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(
        session,
        hid="hid-1001",
        full_name="Banned User",
        username="banned",
    )
    await set_user_banned(session, user)
    message = make_message(text="/start")

    await start.handle_start(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_not_awaited()
    assert user.full_name == "Banned User"


@pytest.mark.asyncio
async def test_start_aborts_when_hid_encoding_fails(
    session: AsyncSession,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_telegram_id: int) -> str:
        raise HIDError("HID is unavailable")

    monkeypatch.setattr(start, "telegram_id_to_hid", fail)
    message = make_message(text="/start")

    await start.handle_start(
        message,
        state=FakeFSMContext(),
        session=session,
    )

    message.answer.assert_not_awaited()
    assert await get_user(session, "hid-1001") is None


@pytest.mark.asyncio
async def test_database_middleware_injects_session_and_commits() -> None:
    factory = FakeSessionFactory()
    middleware = DatabaseMiddleware(factory)  # type: ignore[arg-type]
    seen: dict[str, Any] = {}

    async def handler(event: object, data: dict[str, Any]) -> str:
        seen.update(data)
        return "handled"

    result = await middleware(handler, object(), {})

    assert result == "handled"
    assert isinstance(seen["session"], FakeSession)
    session = factory.sessions[0]
    assert session.committed
    assert not session.rolled_back
    assert session.closed


@pytest.mark.asyncio
async def test_database_middleware_rolls_back_on_error() -> None:
    factory = FakeSessionFactory()
    middleware = DatabaseMiddleware(factory)  # type: ignore[arg-type]

    async def handler(event: object, data: dict[str, Any]) -> None:
        raise RuntimeError("handler failed")

    with pytest.raises(RuntimeError):
        await middleware(handler, object(), {})

    session = factory.sessions[0]
    assert session.rolled_back
    assert not session.committed
    assert session.closed


def test_dispatcher_includes_start_router() -> None:
    dispatcher = create_dispatcher(FakeSessionFactory())  # type: ignore[arg-type]

    assert start.router in dispatcher.sub_routers


@pytest.mark.asyncio
async def test_run_bot_requires_database_url() -> None:
    config = Config(bot_token="123456:fake")

    with pytest.raises(ConfigError):
        await run_bot(config)
