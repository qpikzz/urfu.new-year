"""Handler for /start, the registration captcha and consent."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.content.texts import (
    CAPTCHA_FAILED,
    CAPTCHA_PASSED,
    START_WELCOME,
    format_captcha_wrong,
    format_consent_text,
)
from app.db.requests import (
    create_user,
    get_circle,
    get_user,
    mark_user_registered,
    set_user_banned,
    update_user_identity,
)
from app.hid import HIDError, telegram_id_to_hid
from app.keyboards import (
    CAPTCHA_CALLBACK_PREFIX,
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_CONTINUE_CALLBACK,
    captcha_keyboard,
    consent_continue_keyboard,
    consent_keyboard,
)
from app.services import (
    CAPTCHA_CORRECT_KEY,
    CAPTCHA_KIND_KEY,
    CAPTCHA_MAX_ATTEMPTS,
    CAPTCHA_OPTIONS_KEY,
    CAPTCHA_PASSED_KEY,
    CAPTCHA_WRONG_ATTEMPTS_KEY,
    CONSENT_ACCEPTED_KEY,
    REGISTRATION_STEP_KEY,
    RegistrationStep,
    build_menu_text,
    captcha_attempts_left,
    challenge_from_state,
    create_captcha_challenge,
    is_registration_complete,
    resume_registration,
    wrong_attempts_from_state,
)

logger = logging.getLogger(__name__)

router = Router(name="start")


async def _send_captcha_question(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    challenge = challenge_from_state(data)
    if challenge is None:
        challenge = create_captcha_challenge()
        values = challenge.as_state()
        values[CAPTCHA_WRONG_ATTEMPTS_KEY] = wrong_attempts_from_state(data)
        await state.update_data(values)

    await message.answer(
        challenge.question(),
        reply_markup=captcha_keyboard(challenge.options),
    )


async def _mark_captcha_passed(state: FSMContext) -> None:
    await state.update_data(
        {
            CAPTCHA_PASSED_KEY: True,
            REGISTRATION_STEP_KEY: RegistrationStep.CONSENT.value,
            CAPTCHA_CORRECT_KEY: None,
            CAPTCHA_KIND_KEY: None,
            CAPTCHA_OPTIONS_KEY: None,
            CAPTCHA_WRONG_ATTEMPTS_KEY: 0,
        }
    )


def _consent_text(config: Config | None) -> str:
    return format_consent_text(
        privacy_url=config.privacy_url if config and config.privacy_url else "",
        terms_url=config.terms_url if config and config.terms_url else "",
    )


async def _send_consent_question(
    message: Message,
    config: Config | None,
) -> None:
    await message.answer(
        _consent_text(config),
        reply_markup=consent_keyboard(),
    )


@router.message(CommandStart())
async def handle_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    config: Config | None = None,
) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        return

    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Start flow aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is not None and user.is_banned:
        return

    full_name = telegram_user.full_name
    username = telegram_user.username or "0"
    created = user is None
    if user is None:
        user = await create_user(
            session,
            hid=hid,
            full_name=full_name,
            username=username,
        )
    else:
        await update_user_identity(
            session,
            user,
            full_name=full_name,
            username=username,
        )

    if is_registration_complete(user):
        circle = await get_circle(session, user.cir_id) if user.cir_id else None
        await message.answer(build_menu_text(user, circle))
        logger.info("Start flow: hid=%s step=complete", user.hid)
        return

    step = await resume_registration(state, user)
    if created:
        await message.answer(START_WELCOME)
    if step == RegistrationStep.CAPTCHA:
        await _send_captcha_question(message, state)
    elif step == RegistrationStep.CONSENT:
        await _send_consent_question(message, config)
    logger.info("Start flow: hid=%s step=%s", user.hid, step.value)


@router.callback_query(F.data.startswith(CAPTCHA_CALLBACK_PREFIX))
async def handle_captcha_answer(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    telegram_user = callback.from_user
    if telegram_user is None or callback.message is None:
        return

    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Captcha aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is None or user.is_banned:
        return

    data = await state.get_data()
    if data.get(REGISTRATION_STEP_KEY) != RegistrationStep.CAPTCHA.value:
        return

    challenge = challenge_from_state(data)
    if challenge is None:
        return

    answer = (callback.data or "").removeprefix(CAPTCHA_CALLBACK_PREFIX)
    if answer == challenge.correct:
        await _mark_captcha_passed(state)
        await callback.answer()
        await callback.message.edit_text(
            CAPTCHA_PASSED,
            reply_markup=consent_continue_keyboard(),
        )
        logger.info("Captcha passed: hid=%s", user.hid)
        return

    attempts = wrong_attempts_from_state(data) + 1
    if attempts >= CAPTCHA_MAX_ATTEMPTS:
        await set_user_banned(session, user)
        await state.clear()
        await callback.answer()
        await callback.message.edit_text(CAPTCHA_FAILED, reply_markup=None)
        logger.info("Captcha failed: hid=%s attempts=%s", user.hid, attempts)
        return

    new_challenge = create_captcha_challenge()
    values = new_challenge.as_state()
    values[CAPTCHA_WRONG_ATTEMPTS_KEY] = attempts
    await state.update_data(values)
    await callback.answer(
        format_captcha_wrong(captcha_attempts_left(attempts))
    )
    await callback.message.edit_text(
        new_challenge.question(),
        reply_markup=captcha_keyboard(new_challenge.options),
    )
    logger.info(
        "Captcha wrong: hid=%s attempts=%s",
        user.hid,
        attempts,
    )


@router.callback_query(F.data == CONSENT_CONTINUE_CALLBACK)
async def handle_consent_continue(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    config: Config | None = None,
) -> None:
    telegram_user = callback.from_user
    if telegram_user is None or callback.message is None:
        return

    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Consent aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is None or user.is_banned:
        return

    data = await state.get_data()
    if data.get(REGISTRATION_STEP_KEY) != RegistrationStep.CONSENT.value:
        return

    await callback.answer()
    await callback.message.edit_text(
        _consent_text(config),
        reply_markup=consent_keyboard(),
    )
    logger.info("Consent shown: hid=%s", user.hid)


@router.callback_query(F.data == CONSENT_ACCEPT_CALLBACK)
async def handle_consent_accept(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    telegram_user = callback.from_user
    if telegram_user is None or callback.message is None:
        return

    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Consent aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is None or user.is_banned:
        return

    data = await state.get_data()
    if data.get(REGISTRATION_STEP_KEY) != RegistrationStep.CONSENT.value:
        return

    if user.registered_at is None:
        await mark_user_registered(session, user)
    await state.update_data(
        {
            CONSENT_ACCEPTED_KEY: True,
            REGISTRATION_STEP_KEY: RegistrationStep.STATUS.value,
        }
    )
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    logger.info("Consent accepted: hid=%s", user.hid)
