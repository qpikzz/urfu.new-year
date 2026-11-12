"""User-facing texts, labels and formatting helpers (MESSAGES 1-9)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from app.db.enums import CircleStatus, ParticipantStatus, RejectionReason

TEXTS: dict[str, str] = {
    # Registration (MESSAGES 4).
    "start.welcome": (
        "🎉 Привет! Это бот новогодних поздравлений УрФУ.\n"
        "Ты отправляешь один видеокружок с поздравлением, а в новогоднюю ночь "
        "получаешь кружки от двух других участников.\n"
        "Сначала нужно пройти короткую проверку."
    ),
    "captcha.question": "🔎 Нажми на {kind}: «{name}»",
    "captcha.kind.emoji": "эмодзи",
    "captcha.kind.icon": "иконку",
    "captcha.wrong": "❗ Неверно. Осталось попыток: {left}. Попробуй ещё раз.",
    "captcha.failed": "🚫 Проверка не пройдена. Доступ к боту закрыт.",
    "captcha.passed": "✅ Проверка пройдена.",
    "consent.text": (
        "📄 Чтобы продолжить, прочитай документы и прими их.\n"
        "Политика конфиденциальности: {privacy_url}\n"
        "Пользовательское соглашение: {terms_url}"
    ),
    "consent.button": "Принять",
    "status.question": "👤 Кем ты являешься?",
    "institute.question": "🏛 Выбери свой институт.",
    "timezone.question": (
        "🌐 Укажи свой часовой пояс: число часов относительно UTC.\n"
        "Например, для Екатеринбурга это 5, для Москвы — 3."
    ),
    "timezone.invalid": "❗ Нужно целое число от -12 до 14. Попробуй ещё раз.",
    "registration.done": "✅ Регистрация завершена.",
    # Circle submission (MESSAGES 5).
    "circle.ask": (
        "🎥 Отправь кружок с новогодним поздравлением.\n"
        "Длительность — от 3 до 30 секунд."
    ),
    "circle.wrong_type": (
        "❗ Отправь именно кружок: видеосообщение, записанное круглой кнопкой "
        "в Telegram."
    ),
    "circle.duration_invalid": (
        "❗ Кружок должен длиться от 3 до 30 секунд. Запиши другой."
    ),
    "circle.queued": (
        "✅ Кружок получен и поставлен в очередь на проверку.\n"
        "Статус можно посмотреть в /menu."
    ),
    "circle.in_progress": (
        "⏳ Предыдущий кружок ещё проверяется. Статус можно посмотреть в /menu."
    ),
    "new.unavailable": (
        "⏳ Новый кружок можно отправить после того, как закончится проверка "
        "текущего."
    ),
    "new.ask": "🎥 Отправь новый кружок. Он заменит предыдущий.",
    "new.no_circle": "🎥 У тебя ещё нет кружка. Просто отправь его сообщением.",
    "intake.closed": (
        "⛔ В данный момент получение новых кружков приостановлено! Следите за "
        "ситуацией в нашем канале ({channel_url}) и повторите попытку позже."
    ),
    "unknown.message": (
        "❓ Не понял сообщение. Доступные команды: /menu, /new."
    ),
    # Moderation results (MESSAGES 6).
    "moderation.auto_rejected": (
        "❌ Кружок отклонён.\n"
        "📌 Причина: {reason}\n"
        "⚠ Осталось попыток автопроверки: {auto_left}.\n"
        "Подумай и отправь новый кружок командой /new."
    ),
    "moderation.manual_rejected": (
        "❌ Кружок отклонён администратором.\n"
        "📌 Причина: {reason}\n"
        "⚠ Это твой единственный повтор: при следующем отказе доступ будет "
        "закрыт.\n"
        "Подумай и отправь новый кружок командой /new."
    ),
    "moderation.approved": "✅ Кружок одобрен.",
    "buffer.committed": "✅ Твой кружок добавлен в новогоднюю рассылку.",
    "buffer.rejected": "❌ Кружок отклонён.\n📌 Причина: иная причина",
    "ban.auto_limit": (
        "🚫 Попытки автопроверки закончились. Доступ к боту закрыт."
    ),
    "ban.manual_limit": (
        "🚫 Кружок отклонён повторно.\n"
        "📌 Причина: {reason}\n"
        "Доступ к боту закрыт."
    ),
    # Participant command menu (MESSAGES 7).
    "commands.start": "Регистрация",
    "commands.menu": "Информация о тебе и твоём кружке",
    "commands.new": "Отправить новый кружок",
    "menu.profile": "⭐ Профиль",
    "menu.registered_at": "📆 Дата регистрации: {registered_at}",
    "menu.status": "👤 Статус: {status}",
    "menu.institute": "🏛 Институт: {institute}",
    "menu.timezone": "🌐 Часовой пояс: {timezone}",
    "menu.circle_header": "🎥 Кружок",
    "menu.circle_id": "🆔 ID: {cir_id}",
    "menu.circle_status": "📍 Статус: {circle_status}",
    "menu.circle_duration": "⏱ Длительность: {duration} с",
    "menu.circle_sent_at": "📆 Отправлен: {sent_at}",
    "menu.circle_rejection_reason": "❗ Причина отказа: {reason}",
    "menu.no_circle": "🎥 Кружок: не отправлен",
    # New Year mailing (MESSAGES 8).
    "mailing.greeting": "🎉 Поздравление от {full_name}",
    # Moderation buttons (MESSAGES 9.1).
    "moderation.approve_button": "✅",
    "moderation.reject_button": "❌",
    "rejection.cancel_button": "Отмена, принять",
    "rejection.profanity_button": "Содержит нецензурную лексику",
    "rejection.shocking_content_button": "Содержит шокирующий контент",
    "rejection.advertising_button": "Реклама",
    "rejection.other_button": "Иная причина",
    # Intake notifications (MESSAGES 9.2).
    "intake.admin_closed": (
        "🔒 Приём кружков закрыт\n"
        "🕒 Время: {time} ЕКБ\n"
        "📌 Причина: {reason}"
    ),
    "intake.admin_reopened": (
        "🔓 Приём кружков открыт\n"
        "🕒 Время: {time} ЕКБ\n"
        "📌 Причина закрытия устранена: {reason}"
    ),
    "close.on": "🔒 Приём кружков закрыт вручную.",
    "close.off": "🔓 Ручное закрытие приёма снято.",
    "intake.reason.scheduled": "закрытие по расписанию",
    "intake.reason.manual": "закрыт вручную командой /close",
    "intake.reason.environment": "закрыт флагом в настройках",
    "intake.reason.cpu": (
        "загрузка CPU выше 90% дольше 3 минут (сейчас {value}%)"
    ),
    "intake.reason.disk": (
        "свободного места на диске меньше 1 ГБ (сейчас {value} ГБ)"
    ),
    "intake.reason.queue": (
        "в очереди автопроверки больше 1000 участников (сейчас {value})"
    ),
    # Command responses (MESSAGES 9.3).
    "look.not_found": "❗ Кружок {cir_id} не найден.",
    "ban.done": "🚫 Участник {hid} заблокирован.",
    "ban.not_found": "❗ Участник {hid} не найден.",
    "accept.done": "✅ Статус кружка {cir_id} изменён на 2.",
    "reject.done": "✅ Статус кружка {cir_id} изменён на 3.",
    "status.not_found": "❗ Кружок {cir_id} не найден.",
    "send.ask": (
        "📣 Отправь сообщение для рассылки. Оно уйдёт всем пользователям в "
        "точно таком же виде."
    ),
    "send.started": "⏳ Рассылка запущена.",
    "send.done": (
        "✅ Рассылка завершена.\n"
        "📤 Отправлено: {sent}\n"
        "📥 Получили: {received}\n"
        "🕒 Начало: {started} ЕКБ\n"
        "🕒 Конец: {finished} ЕКБ"
    ),
    "stats.template": (
        "📊 Статистика\n"
        "👥 Всего пользователей: {total_users}\n"
        "📝 Зарегистрировано: {registered}\n"
        "🎥 Кружков всего: {circles_total}\n"
        "📆 Отправлено сегодня: {circles_today}\n"
        "✅ Одобрено: {approved}\n"
        "❌ Отклонено вручную: {rejected_manual}\n"
        "🤖 Отклонено автоматически: {rejected_auto}"
    ),
}

START_WELCOME = TEXTS["start.welcome"]
CAPTCHA_QUESTION = TEXTS["captcha.question"]
CAPTCHA_KIND_EMOJI = TEXTS["captcha.kind.emoji"]
CAPTCHA_KIND_ICON = TEXTS["captcha.kind.icon"]
CAPTCHA_WRONG = TEXTS["captcha.wrong"]
CAPTCHA_FAILED = TEXTS["captcha.failed"]
CAPTCHA_PASSED = TEXTS["captcha.passed"]
CONSENT_TEXT = TEXTS["consent.text"]
CONSENT_BUTTON = TEXTS["consent.button"]
# Author-approved addition: continue button between captcha and consent.
CONSENT_CONTINUE_BUTTON = "Продолжить"
STATUS_QUESTION = TEXTS["status.question"]
INSTITUTE_QUESTION = TEXTS["institute.question"]
TIMEZONE_QUESTION = TEXTS["timezone.question"]
TIMEZONE_INVALID = TEXTS["timezone.invalid"]
REGISTRATION_DONE = TEXTS["registration.done"]

CIRCLE_ASK = TEXTS["circle.ask"]
CIRCLE_WRONG_TYPE = TEXTS["circle.wrong_type"]
CIRCLE_DURATION_INVALID = TEXTS["circle.duration_invalid"]
CIRCLE_QUEUED = TEXTS["circle.queued"]
CIRCLE_IN_PROGRESS = TEXTS["circle.in_progress"]
NEW_UNAVAILABLE = TEXTS["new.unavailable"]
NEW_ASK = TEXTS["new.ask"]
NEW_NO_CIRCLE = TEXTS["new.no_circle"]
INTAKE_CLOSED = TEXTS["intake.closed"]
UNKNOWN_MESSAGE = TEXTS["unknown.message"]

MODERATION_AUTO_REJECTED = TEXTS["moderation.auto_rejected"]
MODERATION_MANUAL_REJECTED = TEXTS["moderation.manual_rejected"]
MODERATION_APPROVED = TEXTS["moderation.approved"]
BUFFER_COMMITTED = TEXTS["buffer.committed"]
BUFFER_REJECTED = TEXTS["buffer.rejected"]
BAN_AUTO_LIMIT = TEXTS["ban.auto_limit"]
BAN_MANUAL_LIMIT = TEXTS["ban.manual_limit"]

COMMAND_DESCRIPTIONS = {
    "start": TEXTS["commands.start"],
    "menu": TEXTS["commands.menu"],
    "new": TEXTS["commands.new"],
}
MENU_NO_CIRCLE = TEXTS["menu.no_circle"]
MAILING_GREETING = TEXTS["mailing.greeting"]

MODERATION_APPROVE_BUTTON = TEXTS["moderation.approve_button"]
MODERATION_REJECT_BUTTON = TEXTS["moderation.reject_button"]
REJECTION_CANCEL_BUTTON = TEXTS["rejection.cancel_button"]
REJECTION_PROFANITY_BUTTON = TEXTS["rejection.profanity_button"]
REJECTION_SHOCKING_CONTENT_BUTTON = TEXTS["rejection.shocking_content_button"]
REJECTION_ADVERTISING_BUTTON = TEXTS["rejection.advertising_button"]
REJECTION_OTHER_BUTTON = TEXTS["rejection.other_button"]

INTAKE_ADMIN_CLOSED = TEXTS["intake.admin_closed"]
INTAKE_ADMIN_REOPENED = TEXTS["intake.admin_reopened"]
CLOSE_ON = TEXTS["close.on"]
CLOSE_OFF = TEXTS["close.off"]

LOOK_NOT_FOUND = TEXTS["look.not_found"]
BAN_DONE = TEXTS["ban.done"]
BAN_NOT_FOUND = TEXTS["ban.not_found"]
ACCEPT_DONE = TEXTS["accept.done"]
REJECT_DONE = TEXTS["reject.done"]
STATUS_NOT_FOUND = TEXTS["status.not_found"]
SEND_ASK = TEXTS["send.ask"]
SEND_STARTED = TEXTS["send.started"]
SEND_DONE = TEXTS["send.done"]
STATS_TEMPLATE = TEXTS["stats.template"]

PARTICIPANT_STATUS_LABELS = {
    ParticipantStatus.APPLICANT: "Абитуриент (школьник)",
    ParticipantStatus.URFU_STUDENT: "Студент УрФУ",
    ParticipantStatus.OTHER_UNIVERSITY_STUDENT: "Студент другого вуза",
    ParticipantStatus.STUDENT_PARENT: "Родитель студента",
    ParticipantStatus.UNIVERSITY_EMPLOYEE: "Работник вуза",
    ParticipantStatus.OTHER: "Прочее",
}

CIRCLE_STATUS_LABELS = {
    CircleStatus.PENDING_AUTO: "Ожидает автопроверки",
    CircleStatus.PENDING_MANUAL: "Ожидает проверки администратором",
    CircleStatus.APPROVED: "Одобрен",
    CircleStatus.REJECTED: "Отклонён",
}
BUFFERED_CIRCLE_STATUS_LABEL = "Одобрен, ожидает добавления в рассылку"

REJECTION_REASON_LABELS = {
    RejectionReason.PROFANITY: "нецензурная лексика",
    RejectionReason.SHOCKING_CONTENT: "шокирующий контент",
    RejectionReason.ADVERTISING: "реклама",
    RejectionReason.OTHER: "иная причина",
}

CAPTCHA_EMOJI_NAMES = {
    "❤️": "Сердце",
    "⚡": "Молния",
    "🦴": "Кость",
    "👁": "Глаз",
    "🦷": "Зуб",
    "🦊": "Лиса",
    "🐷": "Свинья",
    "🐭": "Мышь",
    "🐥": "Цыплёнок",
    "🍉": "Арбуз",
    "🍎": "Яблоко",
    "🧊": "Лёд",
    "⭐": "Звезда",
    "🔥": "Огонь",
    "⚽": "Мяч",
    "🎲": "Кубик",
    "💿": "Диск",
    "📕": "Книга",
    "✏": "Карандаш",
    "🧻": "Туалетная бумага",
}
CAPTCHA_EMOJIS = tuple(CAPTCHA_EMOJI_NAMES)

_TEXT_EMOJIS = frozenset(
    {
        "🎉",
        "🔎",
        "❗",
        "🚫",
        "✅",
        "📄",
        "👤",
        "🏛",
        "🌐",
        "🎥",
        "⛔",
        "❓",
        "❌",
        "📌",
        "⚠",
        "⏳",
        "🔒",
        "🕒",
        "🔓",
        "📣",
        "📤",
        "📥",
        "⭐",
        "📆",
        "🆔",
        "📍",
        "⏱",
        "📊",
        "👥",
        "📝",
        "🤖",
    }
)
EMOJI_TOKENS = frozenset(CAPTCHA_EMOJI_NAMES) | _TEXT_EMOJIS
_EMOJI_PATTERN = re.compile(
    "|".join(
        re.escape(token)
        for token in sorted(EMOJI_TOKENS, key=len, reverse=True)
    )
)


def validate_text_formatting(text: str) -> None:
    """Raise when a text breaks the emoji rules from MESSAGES 2."""
    for line in text.splitlines():
        matches = list(_EMOJI_PATTERN.finditer(line))
        if len(matches) > 1:
            raise ValueError(f"line contains more than one emoji: {line!r}")
        if matches and matches[0].start() != 0:
            raise ValueError(f"emoji is not at the start of a line: {line!r}")


def _localized(value: datetime, timezone_offset: int | None) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if timezone_offset is None:
        return value.astimezone(UTC)
    return value.astimezone(timezone(timedelta(hours=timezone_offset)))


def format_timezone(offset: int) -> str:
    sign = "+" if offset >= 0 else "-"
    return f"UTC{sign}{abs(offset)}"


def format_date(value: datetime | None, timezone_offset: int | None = None) -> str:
    if value is None:
        return ""
    return _localized(value, timezone_offset).strftime("%d.%m.%Y")


def format_time(value: datetime | None, timezone_offset: int | None = None) -> str:
    if value is None:
        return ""
    return _localized(value, timezone_offset).strftime("%H:%M")


def format_captcha_question(kind: str, name: str) -> str:
    return CAPTCHA_QUESTION.format(kind=kind, name=name)


def format_captcha_wrong(left: int) -> str:
    return CAPTCHA_WRONG.format(left=left)


def format_consent_text(*, privacy_url: str, terms_url: str) -> str:
    return CONSENT_TEXT.format(privacy_url=privacy_url, terms_url=terms_url)


def format_intake_closed(*, channel_url: str) -> str:
    return INTAKE_CLOSED.format(channel_url=channel_url)


def format_auto_rejected(*, reason: RejectionReason, auto_left: int) -> str:
    return MODERATION_AUTO_REJECTED.format(
        reason=REJECTION_REASON_LABELS[reason],
        auto_left=auto_left,
    )


def format_manual_rejected(*, reason: RejectionReason) -> str:
    return MODERATION_MANUAL_REJECTED.format(
        reason=REJECTION_REASON_LABELS[reason],
    )


def format_ban_manual_limit(*, reason: RejectionReason) -> str:
    return BAN_MANUAL_LIMIT.format(reason=REJECTION_REASON_LABELS[reason])


def format_greeting_from(full_name: str) -> str:
    return MAILING_GREETING.format(full_name=full_name)


def format_intake_admin_closed(*, time: str, reason: str) -> str:
    return INTAKE_ADMIN_CLOSED.format(time=time, reason=reason)


def format_intake_admin_reopened(*, time: str, reason: str) -> str:
    return INTAKE_ADMIN_REOPENED.format(time=time, reason=reason)


def format_intake_reason_cpu(value: int | float) -> str:
    return TEXTS["intake.reason.cpu"].format(value=value)


def format_intake_reason_disk(value: int | float) -> str:
    return TEXTS["intake.reason.disk"].format(value=value)


def format_intake_reason_queue(value: int) -> str:
    return TEXTS["intake.reason.queue"].format(value=value)


def format_look_not_found(cir_id: int) -> str:
    return LOOK_NOT_FOUND.format(cir_id=cir_id)


def format_ban_done(hid: str) -> str:
    return BAN_DONE.format(hid=hid)


def format_ban_not_found(hid: str) -> str:
    return BAN_NOT_FOUND.format(hid=hid)


def format_accept_done(cir_id: int) -> str:
    return ACCEPT_DONE.format(cir_id=cir_id)


def format_reject_done(cir_id: int) -> str:
    return REJECT_DONE.format(cir_id=cir_id)


def format_status_not_found(cir_id: int) -> str:
    return STATUS_NOT_FOUND.format(cir_id=cir_id)


def format_send_done(
    *,
    sent: int,
    received: int,
    started: str,
    finished: str,
) -> str:
    return SEND_DONE.format(
        sent=sent,
        received=received,
        started=started,
        finished=finished,
    )


def format_stats(
    *,
    total_users: int,
    registered: int,
    circles_total: int,
    circles_today: int,
    approved: int,
    rejected_manual: int,
    rejected_auto: int,
) -> str:
    return STATS_TEMPLATE.format(
        total_users=total_users,
        registered=registered,
        circles_total=circles_total,
        circles_today=circles_today,
        approved=approved,
        rejected_manual=rejected_manual,
        rejected_auto=rejected_auto,
    )


def format_menu(
    *,
    registered_at: str,
    status: str,
    institute: str | None,
    timezone: str,
    cir_id: int | None = None,
    circle_status: str | None = None,
    duration: int | None = None,
    sent_at: str | None = None,
    rejection_reason: str | None = None,
) -> str:
    lines = [
        TEXTS["menu.profile"],
        TEXTS["menu.registered_at"].format(registered_at=registered_at),
        TEXTS["menu.status"].format(status=status),
    ]
    if institute:
        lines.append(TEXTS["menu.institute"].format(institute=institute))
    lines.append(TEXTS["menu.timezone"].format(timezone=timezone))

    if cir_id is None:
        lines.append(MENU_NO_CIRCLE)
        return "\n".join(lines)

    lines.extend(
        [
            TEXTS["menu.circle_header"],
            TEXTS["menu.circle_id"].format(cir_id=cir_id),
            TEXTS["menu.circle_status"].format(circle_status=circle_status),
            TEXTS["menu.circle_duration"].format(duration=duration),
            TEXTS["menu.circle_sent_at"].format(sent_at=sent_at),
        ]
    )
    if rejection_reason:
        lines.append(
            TEXTS["menu.circle_rejection_reason"].format(
                reason=rejection_reason,
            )
        )

    return "\n".join(lines)


__all__ = [
    "ACCEPT_DONE",
    "BAN_AUTO_LIMIT",
    "BAN_DONE",
    "BAN_MANUAL_LIMIT",
    "BAN_NOT_FOUND",
    "BUFFERED_CIRCLE_STATUS_LABEL",
    "BUFFER_COMMITTED",
    "BUFFER_REJECTED",
    "CAPTCHA_EMOJI_NAMES",
    "CAPTCHA_EMOJIS",
    "CAPTCHA_FAILED",
    "CAPTCHA_KIND_EMOJI",
    "CAPTCHA_KIND_ICON",
    "CAPTCHA_PASSED",
    "CAPTCHA_QUESTION",
    "CAPTCHA_WRONG",
    "CIRCLE_ASK",
    "CIRCLE_DURATION_INVALID",
    "CIRCLE_IN_PROGRESS",
    "CIRCLE_QUEUED",
    "CIRCLE_STATUS_LABELS",
    "CIRCLE_WRONG_TYPE",
    "CLOSE_OFF",
    "CLOSE_ON",
    "COMMAND_DESCRIPTIONS",
    "CONSENT_BUTTON",
    "CONSENT_CONTINUE_BUTTON",
    "CONSENT_TEXT",
    "EMOJI_TOKENS",
    "INSTITUTE_QUESTION",
    "INTAKE_ADMIN_CLOSED",
    "INTAKE_ADMIN_REOPENED",
    "INTAKE_CLOSED",
    "LOOK_NOT_FOUND",
    "MAILING_GREETING",
    "MENU_NO_CIRCLE",
    "MODERATION_APPROVED",
    "MODERATION_APPROVE_BUTTON",
    "MODERATION_AUTO_REJECTED",
    "MODERATION_MANUAL_REJECTED",
    "MODERATION_REJECT_BUTTON",
    "NEW_ASK",
    "NEW_NO_CIRCLE",
    "NEW_UNAVAILABLE",
    "PARTICIPANT_STATUS_LABELS",
    "REGISTRATION_DONE",
    "REJECTION_ADVERTISING_BUTTON",
    "REJECTION_CANCEL_BUTTON",
    "REJECTION_OTHER_BUTTON",
    "REJECTION_PROFANITY_BUTTON",
    "REJECTION_REASON_LABELS",
    "REJECTION_SHOCKING_CONTENT_BUTTON",
    "REJECT_DONE",
    "SEND_ASK",
    "SEND_DONE",
    "SEND_STARTED",
    "START_WELCOME",
    "STATS_TEMPLATE",
    "STATUS_NOT_FOUND",
    "STATUS_QUESTION",
    "TEXTS",
    "TIMEZONE_INVALID",
    "TIMEZONE_QUESTION",
    "UNKNOWN_MESSAGE",
    "format_accept_done",
    "format_auto_rejected",
    "format_ban_done",
    "format_ban_manual_limit",
    "format_ban_not_found",
    "format_captcha_question",
    "format_captcha_wrong",
    "format_consent_text",
    "format_date",
    "format_greeting_from",
    "format_intake_admin_closed",
    "format_intake_admin_reopened",
    "format_intake_closed",
    "format_intake_reason_cpu",
    "format_intake_reason_disk",
    "format_intake_reason_queue",
    "format_look_not_found",
    "format_manual_rejected",
    "format_menu",
    "format_reject_done",
    "format_send_done",
    "format_status_not_found",
    "format_stats",
    "format_time",
    "format_timezone",
    "validate_text_formatting",
]
