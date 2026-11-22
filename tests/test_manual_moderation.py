from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Config
from app.content import texts
from app.db.enums import CircleStatus, RejectedBy, RejectionReason
from app.db.models import Circle, User
from app.db.requests import (
    create_circle,
    create_user,
    get_user,
)
from app.handlers import moderation
from app.hid import HIDError
from app.keyboards import (
    moderation_approve_callback_data,
    moderation_cancel_callback_data,
    moderation_reject_callback_data,
    rejection_callback_data,
)
from app.services import (
    MANUAL_RESUBMISSIONS_LIMIT,
    ModerationAction,
    is_circle_sent_for_review,
    is_manual_resubmission_limit_reached,
    parse_moderation_callback,
    run_manual_moderation_worker,
    send_circle_for_review,
    send_pending_circles,
)

ADMIN_TELEGRAM_ID = 1001
ADMIN_HID = f"hid-{ADMIN_TELEGRAM_ID}"
OWNER_HID = "hid-2002"
ADMIN_CHAT_ID = -1001234567890


def make_config(
    *,
    admin_hids: tuple[str, ...] = (ADMIN_HID,),
    admin_chat_id: int | None = ADMIN_CHAT_ID,
) -> Config:
    return Config(
        bot_token="123456:fake",
        admin_hids=admin_hids,
        admin_chat_id=admin_chat_id,
    )


async def make_circle(
    session: AsyncSession,
    *,
    status: CircleStatus = CircleStatus.PENDING_MANUAL,
    owner_hid: str = OWNER_HID,
    file_id: str = "circle-file-id",
) -> Circle:
    await create_user(session, hid=owner_hid, full_name="Owner")
    return await create_circle(
        session,
        owner_hid=owner_hid,
        file_id=file_id,
        duration=10,
        sent_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        status=status,
    )


@pytest.fixture(autouse=True)
def fake_hid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        moderation,
        "telegram_id_to_hid",
        lambda telegram_id: f"hid-{telegram_id}",
    )
    monkeypatch.setattr(
        moderation,
        "hid_to_telegram_id",
        lambda hid: int(hid.removeprefix("hid-")),
    )


@pytest.mark.parametrize(
    ("used", "expected"),
    [
        (0, False),
        (MANUAL_RESUBMISSIONS_LIMIT, True),
        (MANUAL_RESUBMISSIONS_LIMIT + 1, True),
    ],
)
def test_manual_resubmission_limit(used: int, expected: bool) -> None:
    user = User(hid="hid-1", full_name="Test", resubmissions_used=used)

    assert is_manual_resubmission_limit_reached(user) is expected


def make_admin_callback(
    make_callback,
    make_message,
    *,
    data: str,
    from_user=None,
):
    message = make_message()
    message.delete = AsyncMock()
    return make_callback(data=data, message=message, from_user=from_user)


@pytest.mark.parametrize(
    ("data", "action", "reason"),
    [
        (
            moderation_approve_callback_data(7),
            ModerationAction.APPROVE,
            None,
        ),
        (
            moderation_cancel_callback_data(7),
            ModerationAction.CANCEL,
            None,
        ),
        (
            moderation_reject_callback_data(7),
            ModerationAction.REJECT,
            None,
        ),
        (
            rejection_callback_data(7, RejectionReason.PROFANITY),
            ModerationAction.REJECT,
            RejectionReason.PROFANITY,
        ),
    ],
)
def test_parse_moderation_callback(
    data: str,
    action: ModerationAction,
    reason: RejectionReason | None,
) -> None:
    parsed = parse_moderation_callback(data)

    assert parsed is not None
    assert parsed.action == action
    assert parsed.cir_id == 7
    assert parsed.reason == reason


@pytest.mark.parametrize(
    "data",
    [
        None,
        "",
        "captcha:❤️",
        "moderation:",
        "moderation:approve",
        "moderation:approve:0",
        "moderation:approve:not-a-number",
        "moderation:reject:7:unknown",
        "moderation:cancel:7:extra",
    ],
)
def test_parse_moderation_callback_rejects_invalid_data(
    data: str | None,
) -> None:
    assert parse_moderation_callback(data) is None


@pytest.mark.asyncio
async def test_send_circle_for_review_sends_once(
    session: AsyncSession,
    bot,
) -> None:
    circle = await make_circle(session)
    config = make_config()

    sent = await send_circle_for_review(bot, session, circle, config)

    assert sent is True
    bot.send_video_note.assert_awaited_once()
    kwargs = bot.send_video_note.await_args.kwargs
    assert kwargs["chat_id"] == ADMIN_CHAT_ID
    assert kwargs["video_note"] == "circle-file-id"
    callback_values = [
        button.callback_data
        for row in kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert moderation_approve_callback_data(circle.id) in callback_values
    assert moderation_reject_callback_data(circle.id) in callback_values
    assert await is_circle_sent_for_review(session, circle.id)

    assert await send_circle_for_review(bot, session, circle, config) is False
    assert bot.send_video_note.await_count == 1


@pytest.mark.asyncio
async def test_send_circle_without_admin_chat_is_skipped(
    session: AsyncSession,
    bot,
) -> None:
    circle = await make_circle(session)
    config = make_config(admin_chat_id=None)

    sent = await send_circle_for_review(bot, session, circle, config)

    assert sent is False
    bot.send_video_note.assert_not_awaited()
    assert not await is_circle_sent_for_review(session, circle.id)


@pytest.mark.asyncio
async def test_send_failure_removes_marker(
    session: AsyncSession,
    bot,
) -> None:
    circle = await make_circle(session)
    config = make_config()
    bot.send_video_note.side_effect = RuntimeError("Telegram is unavailable")

    with pytest.raises(RuntimeError):
        await send_circle_for_review(bot, session, circle, config)

    assert not await is_circle_sent_for_review(session, circle.id)


@pytest.mark.asyncio
async def test_send_pending_circles_only_status_one(
    session: AsyncSession,
    bot,
) -> None:
    pending = await make_circle(session, status=CircleStatus.PENDING_MANUAL)
    await make_circle(
        session,
        status=CircleStatus.PENDING_AUTO,
        owner_hid="hid-2003",
    )
    await make_circle(
        session,
        status=CircleStatus.APPROVED,
        owner_hid="hid-2004",
    )
    await make_circle(
        session,
        status=CircleStatus.REJECTED,
        owner_hid="hid-2005",
    )

    sent = await send_pending_circles(bot, session, make_config())

    assert sent == 1
    bot.send_video_note.assert_awaited_once()
    kwargs = bot.send_video_note.await_args.kwargs
    assert kwargs["video_note"] == pending.file_id


@pytest.mark.asyncio
async def test_manual_moderation_worker_sends_and_stops(
    db_engine,
    bot,
) -> None:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await make_circle(session)
        await session.commit()

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_manual_moderation_worker(
            factory,
            bot,
            make_config(),
            interval=0.01,
            stop_event=stop_event,
        )
    )
    await asyncio.sleep(0.05)
    stop_event.set()
    await asyncio.wait_for(task, timeout=1)

    bot.send_video_note.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_approves_circle(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=moderation_approve_callback_data(circle.id),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    callback.answer.assert_awaited_once()
    callback.message.delete.assert_awaited_once()
    assert circle.status == CircleStatus.APPROVED
    assert circle.rejection_reason is None
    assert circle.rejected_by is None
    bot.send_message.assert_awaited_once_with(
        chat_id=2002,
        text=texts.MODERATION_APPROVED,
    )


@pytest.mark.asyncio
async def test_admin_rejects_circle_with_reason(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=rejection_callback_data(circle.id, RejectionReason.PROFANITY),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    callback.message.delete.assert_awaited_once()
    assert circle.status == CircleStatus.REJECTED
    assert circle.rejection_reason == RejectionReason.PROFANITY
    assert circle.rejected_by == RejectedBy.MANUAL
    bot.send_message.assert_awaited_once_with(
        chat_id=2002,
        text=texts.format_manual_rejected(reason=RejectionReason.PROFANITY),
    )


@pytest.mark.asyncio
async def test_cancel_accepts_circle(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=moderation_cancel_callback_data(circle.id),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    assert circle.status == CircleStatus.APPROVED
    bot.send_message.assert_awaited_once_with(
        chat_id=2002,
        text=texts.MODERATION_APPROVED,
    )


@pytest.mark.asyncio
async def test_reject_button_shows_reasons_without_deciding(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=moderation_reject_callback_data(circle.id),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    callback.answer.assert_awaited_once()
    callback.message.edit_reply_markup.assert_awaited_once()
    callback.message.delete.assert_not_awaited()
    assert circle.status == CircleStatus.PENDING_MANUAL
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_admin_callback_is_ignored(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=moderation_approve_callback_data(circle.id),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(admin_hids=("hid-9999",)),
    )

    callback.answer.assert_not_awaited()
    callback.message.delete.assert_not_awaited()
    assert circle.status == CircleStatus.PENDING_MANUAL
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_final_decision_wins(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    config = make_config()
    approve_callback = make_admin_callback(
        make_callback,
        make_message,
        data=moderation_approve_callback_data(circle.id),
    )
    reject_callback = make_admin_callback(
        make_callback,
        make_message,
        data=rejection_callback_data(circle.id, RejectionReason.OTHER),
    )

    await moderation.handle_moderation_callback(
        approve_callback,
        bot=bot,
        session=session,
        config=config,
    )
    await moderation.handle_moderation_callback(
        reject_callback,
        bot=bot,
        session=session,
        config=config,
    )

    assert circle.status == CircleStatus.APPROVED
    assert circle.rejection_reason is None
    reject_callback.message.delete.assert_awaited_once()
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_unknown_circle_callback_is_cleaned_up(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=moderation_approve_callback_data(9999),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    callback.answer.assert_awaited_once()
    callback.message.delete.assert_awaited_once()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_notification_failure_does_not_cancel_decision(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    circle = await make_circle(session)
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=moderation_approve_callback_data(circle.id),
    )

    def fail(_hid: str) -> int:
        raise HIDError("HID module is unavailable")

    monkeypatch.setattr(moderation, "hid_to_telegram_id", fail)

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    assert circle.status == CircleStatus.APPROVED
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_manual_rejection_warns_about_single_resubmission(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    user = await get_user(session, OWNER_HID)
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=rejection_callback_data(circle.id, RejectionReason.OTHER),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    assert user is not None
    assert user.is_banned is False
    bot.send_message.assert_awaited_once_with(
        chat_id=2002,
        text=texts.format_manual_rejected(reason=RejectionReason.OTHER),
    )


@pytest.mark.asyncio
async def test_second_manual_rejection_bans_participant(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    user = await get_user(session, OWNER_HID)
    assert user is not None
    user.resubmissions_used = MANUAL_RESUBMISSIONS_LIMIT
    await session.flush()
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=rejection_callback_data(circle.id, RejectionReason.ADVERTISING),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    assert circle.status == CircleStatus.REJECTED
    assert circle.rejection_reason == RejectionReason.ADVERTISING
    assert circle.rejected_by == RejectedBy.MANUAL
    assert user.is_banned is True
    bot.send_message.assert_awaited_once_with(
        chat_id=2002,
        text=texts.format_ban_manual_limit(reason=RejectionReason.ADVERTISING),
    )


@pytest.mark.asyncio
async def test_banned_participant_is_not_notified_about_rejection(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    user = await get_user(session, OWNER_HID)
    assert user is not None
    user.is_banned = True
    await session.flush()
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=rejection_callback_data(circle.id, RejectionReason.OTHER),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    assert circle.status == CircleStatus.REJECTED
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_ban_persists_when_notification_fails(
    session: AsyncSession,
    bot,
    make_callback,
    make_message,
) -> None:
    circle = await make_circle(session)
    user = await get_user(session, OWNER_HID)
    assert user is not None
    user.resubmissions_used = MANUAL_RESUBMISSIONS_LIMIT
    await session.flush()
    bot.send_message.side_effect = RuntimeError("Telegram is unavailable")
    callback = make_admin_callback(
        make_callback,
        make_message,
        data=rejection_callback_data(circle.id, RejectionReason.PROFANITY),
    )

    await moderation.handle_moderation_callback(
        callback,
        bot=bot,
        session=session,
        config=make_config(),
    )

    assert circle.status == CircleStatus.REJECTED
    assert user.is_banned is True
