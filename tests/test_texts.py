from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.content import texts
from app.db.enums import CircleStatus, ParticipantStatus, RejectionReason

EXPECTED_TEXTS_KEYS = {
    "start.welcome",
    "captcha.question",
    "captcha.kind.emoji",
    "captcha.kind.icon",
    "captcha.wrong",
    "captcha.failed",
    "captcha.passed",
    "consent.text",
    "consent.button",
    "status.question",
    "institute.question",
    "timezone.question",
    "timezone.invalid",
    "registration.done",
    "circle.ask",
    "circle.wrong_type",
    "circle.duration_invalid",
    "circle.queued",
    "circle.in_progress",
    "new.unavailable",
    "new.ask",
    "new.no_circle",
    "intake.closed",
    "unknown.message",
    "moderation.auto_rejected",
    "moderation.manual_rejected",
    "moderation.approved",
    "buffer.committed",
    "buffer.rejected",
    "ban.auto_limit",
    "ban.manual_limit",
    "commands.start",
    "commands.menu",
    "commands.new",
    "menu.profile",
    "menu.registered_at",
    "menu.status",
    "menu.institute",
    "menu.timezone",
    "menu.circle_header",
    "menu.circle_id",
    "menu.circle_status",
    "menu.circle_duration",
    "menu.circle_sent_at",
    "menu.circle_rejection_reason",
    "menu.no_circle",
    "mailing.greeting",
    "moderation.approve_button",
    "moderation.reject_button",
    "rejection.cancel_button",
    "rejection.profanity_button",
    "rejection.shocking_content_button",
    "rejection.advertising_button",
    "rejection.other_button",
    "intake.admin_closed",
    "intake.admin_reopened",
    "close.on",
    "close.off",
    "intake.reason.scheduled",
    "intake.reason.manual",
    "intake.reason.environment",
    "intake.reason.cpu",
    "intake.reason.disk",
    "intake.reason.queue",
    "look.not_found",
    "ban.done",
    "ban.not_found",
    "accept.done",
    "reject.done",
    "status.not_found",
    "send.ask",
    "send.started",
    "send.done",
    "stats.template",
}

EXPECTED_STATIC_TEXTS = {
    "start.welcome": (
        "🎉 Привет! Это бот новогодних поздравлений УрФУ.\n"
        "Ты отправляешь один видеокружок с поздравлением, а в новогоднюю ночь "
        "получаешь кружки от двух других участников.\n"
        "Сначала нужно пройти короткую проверку."
    ),
    "captcha.kind.emoji": "эмодзи",
    "captcha.kind.icon": "иконку",
    "captcha.failed": "🚫 Проверка не пройдена. Доступ к боту закрыт.",
    "captcha.passed": "✅ Проверка пройдена.",
    "consent.button": "Принять",
    "status.question": "👤 Кем ты являешься?",
    "institute.question": "🏛 Выбери свой институт.",
    "timezone.question": (
        "🌐 Укажи свой часовой пояс: число часов относительно UTC.\n"
        "Например, для Екатеринбурга это 5, для Москвы — 3."
    ),
    "timezone.invalid": "❗ Нужно целое число от -12 до 14. Попробуй ещё раз.",
    "registration.done": "✅ Регистрация завершена.",
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
    "unknown.message": "❓ Не понял сообщение. Доступные команды: /menu, /new.",
    "moderation.approved": "✅ Кружок одобрен.",
    "buffer.committed": "✅ Твой кружок добавлен в новогоднюю рассылку.",
    "buffer.rejected": "❌ Кружок отклонён.\n📌 Причина: иная причина",
    "ban.auto_limit": "🚫 Попытки автопроверки закончились. Доступ к боту закрыт.",
    "commands.start": "Регистрация",
    "commands.menu": "Информация о тебе и твоём кружке",
    "commands.new": "Отправить новый кружок",
    "menu.profile": "⭐ Профиль",
    "menu.circle_header": "🎥 Кружок",
    "menu.no_circle": "🎥 Кружок: не отправлен",
    "mailing.greeting": "🎉 Поздравление от {full_name}",
    "moderation.approve_button": "✅",
    "moderation.reject_button": "❌",
    "rejection.cancel_button": "Отмена, принять",
    "rejection.profanity_button": "Содержит нецензурную лексику",
    "rejection.shocking_content_button": "Содержит шокирующий контент",
    "rejection.advertising_button": "Реклама",
    "rejection.other_button": "Иная причина",
    "close.on": "🔒 Приём кружков закрыт вручную.",
    "close.off": "🔓 Ручное закрытие приёма снято.",
    "intake.reason.scheduled": "закрытие по расписанию",
    "intake.reason.manual": "закрыт вручную командой /close",
    "intake.reason.environment": "закрыт флагом в настройках",
    "send.ask": (
        "📣 Отправь сообщение для рассылки. Оно уйдёт всем пользователям в "
        "точно таком же виде."
    ),
    "send.started": "⏳ Рассылка запущена.",
}


def test_text_catalog_contains_every_message_from_spec() -> None:
    assert set(texts.TEXTS) == EXPECTED_TEXTS_KEYS


@pytest.mark.parametrize(("key", "expected"), EXPECTED_STATIC_TEXTS.items())
def test_static_texts_match_spec(key: str, expected: str) -> None:
    assert texts.TEXTS[key] == expected


@pytest.mark.parametrize("text", texts.TEXTS.values())
def test_texts_follow_emoji_formatting_rules(text: str) -> None:
    texts.validate_text_formatting(text)


def test_validator_rejects_emoji_inside_a_line() -> None:
    with pytest.raises(ValueError):
        texts.validate_text_formatting("Текст ❗")


def test_validator_rejects_two_emojis_in_a_line() -> None:
    with pytest.raises(ValueError):
        texts.validate_text_formatting("❗❗ Текст")


def test_participant_status_labels_match_spec() -> None:
    assert texts.PARTICIPANT_STATUS_LABELS == {
        ParticipantStatus.APPLICANT: "Абитуриент (школьник)",
        ParticipantStatus.URFU_STUDENT: "Студент УрФУ",
        ParticipantStatus.OTHER_UNIVERSITY_STUDENT: "Студент другого вуза",
        ParticipantStatus.STUDENT_PARENT: "Родитель студента",
        ParticipantStatus.UNIVERSITY_EMPLOYEE: "Работник вуза",
        ParticipantStatus.OTHER: "Прочее",
    }


def test_circle_status_labels_match_spec() -> None:
    assert texts.CIRCLE_STATUS_LABELS == {
        CircleStatus.PENDING_AUTO: "Ожидает автопроверки",
        CircleStatus.PENDING_MANUAL: "Ожидает проверки администратором",
        CircleStatus.APPROVED: "Одобрен",
        CircleStatus.REJECTED: "Отклонён",
    }
    assert (
        texts.BUFFERED_CIRCLE_STATUS_LABEL
        == "Одобрен, ожидает добавления в рассылку"
    )


def test_rejection_reason_labels_match_spec() -> None:
    assert texts.REJECTION_REASON_LABELS == {
        RejectionReason.PROFANITY: "нецензурная лексика",
        RejectionReason.SHOCKING_CONTENT: "шокирующий контент",
        RejectionReason.ADVERTISING: "реклама",
        RejectionReason.OTHER: "иная причина",
    }


def test_captcha_emojis_match_spec_order_and_names() -> None:
    assert list(texts.CAPTCHA_EMOJI_NAMES.items()) == [
        ("❤️", "Сердце"),
        ("⚡", "Молния"),
        ("🦴", "Кость"),
        ("👁", "Глаз"),
        ("🦷", "Зуб"),
        ("🦊", "Лиса"),
        ("🐷", "Свинья"),
        ("🐭", "Мышь"),
        ("🐥", "Цыплёнок"),
        ("🍉", "Арбуз"),
        ("🍎", "Яблоко"),
        ("🧊", "Лёд"),
        ("⭐", "Звезда"),
        ("🔥", "Огонь"),
        ("⚽", "Мяч"),
        ("🎲", "Кубик"),
        ("💿", "Диск"),
        ("📕", "Книга"),
        ("✏", "Карандаш"),
        ("🧻", "Туалетная бумага"),
    ]
    assert texts.CAPTCHA_EMOJIS == tuple(texts.CAPTCHA_EMOJI_NAMES)


def test_command_descriptions_match_spec() -> None:
    assert texts.COMMAND_DESCRIPTIONS == {
        "start": "Регистрация",
        "menu": "Информация о тебе и твоём кружке",
        "new": "Отправить новый кружок",
    }


def test_registration_formatters() -> None:
    assert (
        texts.format_captcha_question("эмодзи", "Сердце")
        == "🔎 Нажми на эмодзи: «Сердце»"
    )
    assert (
        texts.format_captcha_wrong(2)
        == "❗ Неверно. Осталось попыток: 2. Попробуй ещё раз."
    )
    assert texts.format_consent_text(
        privacy_url="https://privacy.example",
        terms_url="https://terms.example",
    ) == (
        "📄 Чтобы продолжить, прочитай документы и прими их.\n"
        "Политика конфиденциальности: https://privacy.example\n"
        "Пользовательское соглашение: https://terms.example"
    )


def test_consent_continue_button_matches_author_decision() -> None:
    assert texts.CONSENT_CONTINUE_BUTTON == "Продолжить"


def test_circle_and_intake_formatters() -> None:
    assert texts.format_intake_closed(
        channel_url="https://channel.example"
    ) == (
        "⛔ В данный момент получение новых кружков приостановлено! Следите за "
        "ситуацией в нашем канале (https://channel.example) и повторите попытку "
        "позже."
    )
    assert texts.format_greeting_from("Иван Иванов") == (
        "🎉 Поздравление от Иван Иванов"
    )


def test_moderation_formatters() -> None:
    assert texts.format_auto_rejected(
        reason=RejectionReason.PROFANITY,
        auto_left=2,
    ) == (
        "❌ Кружок отклонён.\n"
        "📌 Причина: нецензурная лексика\n"
        "⚠ Осталось попыток автопроверки: 2.\n"
        "Подумай и отправь новый кружок командой /new."
    )
    assert texts.format_manual_rejected(
        reason=RejectionReason.ADVERTISING
    ) == (
        "❌ Кружок отклонён администратором.\n"
        "📌 Причина: реклама\n"
        "⚠ Это твой единственный повтор: при следующем отказе доступ будет "
        "закрыт.\n"
        "Подумай и отправь новый кружок командой /new."
    )
    assert texts.format_ban_manual_limit(
        reason=RejectionReason.OTHER
    ) == (
        "🚫 Кружок отклонён повторно.\n"
        "📌 Причина: иная причина\n"
        "Доступ к боту закрыт."
    )


def test_intake_notification_formatters() -> None:
    assert texts.format_intake_admin_closed(
        time="00:00",
        reason=texts.TEXTS["intake.reason.scheduled"],
    ) == (
        "🔒 Приём кружков закрыт\n"
        "🕒 Время: 00:00 ЕКБ\n"
        "📌 Причина: закрытие по расписанию"
    )
    assert texts.format_intake_admin_reopened(
        time="12:30",
        reason=texts.TEXTS["intake.reason.cpu"],
    ) == (
        "🔓 Приём кружков открыт\n"
        "🕒 Время: 12:30 ЕКБ\n"
        "📌 Причина закрытия устранена: "
        "загрузка CPU выше 90% дольше 3 минут (сейчас {value}%)"
    )
    assert texts.format_intake_reason_cpu(92.5) == (
        "загрузка CPU выше 90% дольше 3 минут (сейчас 92.5%)"
    )
    assert texts.format_intake_reason_disk(0.5) == (
        "свободного места на диске меньше 1 ГБ (сейчас 0.5 ГБ)"
    )
    assert texts.format_intake_reason_queue(1200) == (
        "в очереди автопроверки больше 1000 участников (сейчас 1200)"
    )


def test_admin_command_formatters() -> None:
    assert texts.format_look_not_found(42) == "❗ Кружок 42 не найден."
    assert texts.format_ban_done("hid-1") == "🚫 Участник hid-1 заблокирован."
    assert texts.format_ban_not_found("hid-1") == "❗ Участник hid-1 не найден."
    assert texts.format_accept_done(42) == "✅ Статус кружка 42 изменён на 2."
    assert texts.format_reject_done(42) == "✅ Статус кружка 42 изменён на 3."
    assert texts.format_status_not_found(42) == "❗ Кружок 42 не найден."
    assert texts.format_send_done(
        sent=10,
        received=8,
        started="10:00",
        finished="10:05",
    ) == (
        "✅ Рассылка завершена.\n"
        "📤 Отправлено: 10\n"
        "📥 Получили: 8\n"
        "🕒 Начало: 10:00 ЕКБ\n"
        "🕒 Конец: 10:05 ЕКБ"
    )


def test_stats_formatter() -> None:
    assert texts.format_stats(
        total_users=100,
        registered=90,
        circles_total=80,
        circles_today=7,
        approved=50,
        rejected_manual=10,
        rejected_auto=20,
    ) == (
        "📊 Статистика\n"
        "👥 Всего пользователей: 100\n"
        "📝 Зарегистрировано: 90\n"
        "🎥 Кружков всего: 80\n"
        "📆 Отправлено сегодня: 7\n"
        "✅ Одобрено: 50\n"
        "❌ Отклонено вручную: 10\n"
        "🤖 Отклонено автоматически: 20"
    )


def test_menu_formatter_with_circle_and_institute() -> None:
    assert texts.format_menu(
        registered_at="11.11.2026",
        status="Студент УрФУ",
        institute="ИРИТ-РТФ",
        timezone="UTC+5",
        cir_id=42,
        circle_status="Отклонён",
        duration=15,
        sent_at="11.11.2026 12:30",
        rejection_reason="реклама",
    ) == (
        "⭐ Профиль\n"
        "📆 Дата регистрации: 11.11.2026\n"
        "👤 Статус: Студент УрФУ\n"
        "🏛 Институт: ИРИТ-РТФ\n"
        "🌐 Часовой пояс: UTC+5\n"
        "🎥 Кружок\n"
        "🆔 ID: 42\n"
        "📍 Статус: Отклонён\n"
        "⏱ Длительность: 15 с\n"
        "📆 Отправлен: 11.11.2026 12:30\n"
        "❗ Причина отказа: реклама"
    )


def test_menu_formatter_without_institute_and_circle() -> None:
    assert texts.format_menu(
        registered_at="11.11.2026",
        status="Прочее",
        institute=None,
        timezone="UTC+0",
    ) == (
        "⭐ Профиль\n"
        "📆 Дата регистрации: 11.11.2026\n"
        "👤 Статус: Прочее\n"
        "🌐 Часовой пояс: UTC+0\n"
        "🎥 Кружок: не отправлен"
    )


def test_menu_formatter_omits_rejection_reason_when_absent() -> None:
    result = texts.format_menu(
        registered_at="11.11.2026",
        status="Прочее",
        institute=None,
        timezone="UTC+3",
        cir_id=7,
        circle_status="Одобрен",
        duration=10,
        sent_at="11.11.2026 09:00",
    )

    assert result.endswith("📆 Отправлен: 11.11.2026 09:00")
    assert "Причина отказа" not in result


def test_timezone_and_datetime_formatting() -> None:
    moment = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)

    assert texts.format_timezone(5) == "UTC+5"
    assert texts.format_timezone(-3) == "UTC-3"
    assert texts.format_timezone(0) == "UTC+0"
    assert texts.format_date(moment, 5) == "02.01.2026"
    assert texts.format_time(moment, 5) == "04:30"
    assert texts.format_date(moment) == "01.01.2026"
    assert texts.format_time(moment) == "23:30"
    assert texts.format_date(None) == ""
    assert texts.format_time(None) == ""
