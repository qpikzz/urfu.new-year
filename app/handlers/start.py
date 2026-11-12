"""Handler for /start and the registration steps."""

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
    CIRCLE_ASK,
    INSTITUTE_QUESTION,
    REGISTRATION_DONE,
    START_WELCOME,
    STATUS_QUESTION,
    TIMEZONE_INVALID,
    TIMEZONE_QUESTION,
    format_captcha_wrong,
    format_consent_text,
)
from app.db.requests import (
    create_user,
    get_circle,
    get_user,
    mark_user_registered,
    set_user_banned,
    set_user_institute,
    set_user_status,
    set_user_timezone,
    update_user_identity,
)
from app.hid import HIDError, telegram_id_to_hid
from app.keyboards import (
    CAPTCHA_CALLBACK_PREFIX,
    CONSENT_ACCEPT_CALLBACK,
    CONSENT_CONTINUE_CALLBACK,
    INSTITUTE_CALLBACK_PREFIX,
    STATUS_CALLBACK_PREFIX,
    captcha_keyboard,
    consent_continue_keyboard,
    consent_keyboard,
    institutes_keyboard,
    status_keyboard,
)
from app.services import (
    CAPTCHA_CORRECT_KEY,
    CAPTCHA_KIND_KEY,
    CAPTCHA_MAX_ATTEMPTS,
    CAPTCHA_OPTIONS_KEY,
    CAPTCHA_PASSED_KEY,
    CAPTCHA_WRONG_ATTEMPTS_KEY,
    CONSENT_ACCEPTED_KEY,
    INSTITUTE_REQUIRED_STATUSES,
    REGISTRATION_STEP_KEY,
    RegistrationStep,
    build_menu_text,
    captcha_attempts_left,
    challenge_from_state,
    create_captcha_challenge,
    institute_options,
    is_registration_complete,
    parse_institute,
    parse_status,
    parse_timezone,
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


def _institute_options(config: Config | None) -> tuple[str, ...]:
    return institute_options(config.institutes if config else ())


async def _send_status_question(message: Message) -> None:
    await message.answer(
        STATUS_QUESTION,
        reply_markup=status_keyboard(),
    )


async def _send_institute_question(
    message: Message,
    config: Config | None,
) -> None:
    await message.answer(
        INSTITUTE_QUESTION,
        reply_markup=institutes_keyboard(_institute_options(config)),
    )


async def _send_timezone_question(message: Message) -> None:
    await message.answer(TIMEZONE_QUESTION)


async def _send_registration_complete(message: Message) -> None:
    await message.answer(REGISTRATION_DONE)
    await message.answer(CIRCLE_ASK)


async def send_registration_step(
    message: Message,
    state: FSMContext,
    config: Config | None,
    step: RegistrationStep,
) -> None:
    if step == RegistrationStep.CAPTCHA:
        await _send_captcha_question(message, state)
    elif step == RegistrationStep.CONSENT:
        await _send_consent_question(message, config)
    elif step == RegistrationStep.STATUS:
        await _send_status_question(message)
    elif step == RegistrationStep.INSTITUTE:
        await _send_institute_question(message, config)
    elif step == RegistrationStep.TIMEZONE:
        await _send_timezone_question(message)


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
    await send_registration_step(message, state, config, step)
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
    await _send_status_question(callback.message)
    logger.info("Consent accepted: hid=%s", user.hid)


@router.callback_query(F.data.startswith(STATUS_CALLBACK_PREFIX))
async def handle_status_choice(
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
        logger.error("Profile status aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is None or user.is_banned:
        return

    data = await state.get_data()
    if data.get(REGISTRATION_STEP_KEY) != RegistrationStep.STATUS.value:
        return

    status = parse_status(
        (callback.data or "").removeprefix(STATUS_CALLBACK_PREFIX)
    )
    if status is None:
        return

    await set_user_status(session, user, status)
    await callback.answer()
    if status in INSTITUTE_REQUIRED_STATUSES:
        await state.update_data(
            {REGISTRATION_STEP_KEY: RegistrationStep.INSTITUTE.value}
        )
        await callback.message.edit_text(
            INSTITUTE_QUESTION,
            reply_markup=institutes_keyboard(_institute_options(config)),
        )
    else:
        await state.update_data(
            {REGISTRATION_STEP_KEY: RegistrationStep.TIMEZONE.value}
        )
        await callback.message.edit_text(
            TIMEZONE_QUESTION,
            reply_markup=None,
        )
    logger.info("Profile status selected: hid=%s", user.hid)


@router.callback_query(F.data.startswith(INSTITUTE_CALLBACK_PREFIX))
async def handle_institute_choice(
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
        logger.error("Profile institute aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is None or user.is_banned:
        return

    data = await state.get_data()
    if data.get(REGISTRATION_STEP_KEY) != RegistrationStep.INSTITUTE.value:
        return
    if user.status not in INSTITUTE_REQUIRED_STATUSES:
        return

    institute = parse_institute(
        (callback.data or "").removeprefix(INSTITUTE_CALLBACK_PREFIX),
        _institute_options(config),
    )
    if institute is None:
        return

    await set_user_institute(session, user, institute)
    await state.update_data(
        {REGISTRATION_STEP_KEY: RegistrationStep.TIMEZONE.value}
    )
    await callback.answer()
    await callback.message.edit_text(TIMEZONE_QUESTION, reply_markup=None)
    logger.info("Profile institute selected: hid=%s", user.hid)


@router.message(F.text, ~F.text.startswith("/"))
async def handle_timezone_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        return

    try:
        hid = telegram_id_to_hid(telegram_user.id)
    except HIDError:
        logger.error("Profile timezone aborted: HID encoding failed")
        return

    user = await get_user(session, hid)
    if user is None or user.is_banned or user.status is None:
        return
    if (
        user.status in INSTITUTE_REQUIRED_STATUSES
        and user.institute is None
    ):
        return

    data = await state.get_data()
    if data.get(REGISTRATION_STEP_KEY) != RegistrationStep.TIMEZONE.value:
        return

    offset = parse_timezone(message.text)
    if offset is None:
        await message.answer(TIMEZONE_INVALID)
        logger.info("Profile timezone invalid: hid=%s", user.hid)
        return

    if user.registered_at is None:
        await mark_user_registered(session, user)
    await set_user_timezone(session, user, offset)
    await state.update_data(
        {REGISTRATION_STEP_KEY: RegistrationStep.COMPLETE.value}
    )
    await _send_registration_complete(message)
    logger.info("Profile complete: hid=%s", user.hid)
