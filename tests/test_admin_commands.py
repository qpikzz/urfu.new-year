from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import texts
from app.db.enums import (
    CircleStatus,
    ParticipantStatus,
    RejectedBy,
    RejectionReason,
)
from app.db.requests import (
    create_circle,
    create_user,
    mark_user_registered,
    set_user_circle,
    set_user_status,
    set_user_timezone,
)
from app.handlers import about, accept, ban, look, reject
from app.services import build_menu_text, command_argument, parse_cir_id


async def make_registered_user(session: AsyncSession) -> Any:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    await mark_user_registered(
        session,
        user,
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await set_user_status(session, user, ParticipantStatus.APPLICANT)
    await set_user_timezone(session, user, 5)
    return user


async def make_circle(
    session: AsyncSession,
    *,
    status: CircleStatus = CircleStatus.PENDING_MANUAL,
) -> Any:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    circle = await create_circle(
        session,
        owner_hid=user.hid,
        file_id="file-id",
        duration=10,
        sent_at=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
        status=status,
    )
    return user, circle


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/look 42", "42"),
        ("/look@urfu_bot 42", "42"),
        ("  /ban   hid-1001  ", "hid-1001"),
        ("/look", None),
        ("/look    ", None),
        ("/look 42 extra", "42 extra"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_command_argument(text: str | None, expected: str | None) -> None:
    assert command_argument(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/look 42", 42),
        ("/accept@urfu_bot 7", 7),
        ("/look 0", None),
        ("/look -1", None),
        ("/look abc", None),
        ("/look 42 extra", None),
        ("/look", None),
        (None, None),
    ],
)
def test_parse_cir_id(text: str | None, expected: int | None) -> None:
    assert parse_cir_id(text) == expected


@pytest.mark.asyncio
async def test_look_sends_found_circle(
    session: AsyncSession,
    make_message,
) -> None:
    _, circle = await make_circle(session)
    message = make_message(text=f"/look {circle.id}")

    await look.handle_look(message, session=session)

    message.answer_video_note.assert_awaited_once_with(video_note="file-id")
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_look_reports_missing_circle(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/look 999")

    await look.handle_look(message, session=session)

    message.answer.assert_awaited_once_with(texts.format_look_not_found(999))
    message.answer_video_note.assert_not_awaited()


@pytest.mark.asyncio
async def test_look_ignores_invalid_argument(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/look abc")

    await look.handle_look(message, session=session)

    message.answer.assert_not_awaited()
    message.answer_video_note.assert_not_awaited()


@pytest.mark.asyncio
async def test_ban_bans_participant(
    session: AsyncSession,
    make_message,
) -> None:
    user = await create_user(session, hid="hid-1001", full_name="Test User")
    message = make_message(text="/ban hid-1001")

    await ban.handle_ban(message, session=session)

    assert user.is_banned is True
    message.answer.assert_awaited_once_with(texts.format_ban_done("hid-1001"))


@pytest.mark.asyncio
async def test_ban_reports_unknown_participant(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/ban hid-404")

    await ban.handle_ban(message, session=session)

    message.answer.assert_awaited_once_with(texts.format_ban_not_found("hid-404"))


@pytest.mark.asyncio
async def test_ban_ignores_missing_argument(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/ban")

    await ban.handle_ban(message, session=session)

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_sets_status_two(
    session: AsyncSession,
    make_message,
) -> None:
    _, circle = await make_circle(session)
    message = make_message(text=f"/accept {circle.id}")

    await accept.handle_accept(message, session=session)

    assert circle.status == CircleStatus.APPROVED
    message.answer.assert_awaited_once_with(
        texts.format_accept_done(circle.id)
    )


@pytest.mark.asyncio
async def test_accept_overrides_any_status(
    session: AsyncSession,
    make_message,
) -> None:
    _, circle = await make_circle(session, status=CircleStatus.REJECTED)
    message = make_message(text=f"/accept {circle.id}")

    await accept.handle_accept(message, session=session)

    assert circle.status == CircleStatus.APPROVED
    assert circle.rejection_reason is None
    assert circle.rejected_by is None


@pytest.mark.asyncio
async def test_accept_reports_missing_circle(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/accept 999")

    await accept.handle_accept(message, session=session)

    message.answer.assert_awaited_once_with(texts.format_status_not_found(999))


@pytest.mark.asyncio
async def test_accept_ignores_invalid_argument(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/accept abc")

    await accept.handle_accept(message, session=session)

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_sets_status_three_with_other_reason(
    session: AsyncSession,
    make_message,
) -> None:
    _, circle = await make_circle(session, status=CircleStatus.APPROVED)
    message = make_message(text=f"/reject {circle.id}")

    await reject.handle_reject(message, session=session)

    assert circle.status == CircleStatus.REJECTED
    assert circle.rejection_reason == RejectionReason.OTHER
    assert circle.rejected_by == RejectedBy.MANUAL
    message.answer.assert_awaited_once_with(
        texts.format_reject_done(circle.id)
    )


@pytest.mark.asyncio
async def test_reject_reports_missing_circle(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/reject 999")

    await reject.handle_reject(message, session=session)

    message.answer.assert_awaited_once_with(texts.format_status_not_found(999))


@pytest.mark.asyncio
async def test_reject_ignores_invalid_argument(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/reject abc")

    await reject.handle_reject(message, session=session)

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_about_prints_menu_information(
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
    message = make_message(text="/about hid-1001")

    await about.handle_about(message, session=session)

    message.answer.assert_awaited_once_with(build_menu_text(user, circle))


@pytest.mark.asyncio
async def test_about_ignores_unknown_participant(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/about hid-404")

    await about.handle_about(message, session=session)

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_about_ignores_incomplete_registration(
    session: AsyncSession,
    make_message,
) -> None:
    await create_user(session, hid="hid-1001", full_name="Test User")
    message = make_message(text="/about hid-1001")

    await about.handle_about(message, session=session)

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_about_ignores_missing_argument(
    session: AsyncSession,
    make_message,
) -> None:
    message = make_message(text="/about")

    await about.handle_about(message, session=session)

    message.answer.assert_not_awaited()
