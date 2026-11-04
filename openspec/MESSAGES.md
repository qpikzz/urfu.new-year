# MESSAGES

All user-facing texts of Urfu27bot: wording, buttons and formatting rules. All texts are in Russian. When this file is changed, the code is updated to match it; the code must not contain texts that are not listed here.

## 1. Tone and style

- Calm, neutral, direct. Short sentences. States the fact first and the next step second.
- Addresses the participant informally ("ты").
- No slang, no jokes, no pressure, no excessive punctuation. The exclamation mark is used only where a text below contains it.
- Does not apologize and does not explain internal mechanics unless the text below does.

## 2. Formatting rules

- Emoji are used only at the beginning of a line, never inside a line. A line may start with at most one emoji.
- The exceptions are the captcha buttons and the moderation buttons ✅ and ❌.
- No other decorative formatting (bold, italics, code) is used in the texts below.
- `\n` in a text means a line break. Text in `{braces}` is a placeholder substituted by the bot.
- Dates: `DD.MM.YYYY`. Time: `HH:MM`. Dates shown to a participant are in the participant's time zone if it is set, otherwise in UTC. Times shown to administrators are in Yekaterinburg time and are marked "ЕКБ".
- Time zone display: `UTC+5`, `UTC-3`, `UTC+0`.

## 3. Placeholders and labels

### 3.1. Participant statuses (`users.status`)

| Value | Label |
|---|---|
| `applicant` | Абитуриент (школьник) |
| `urfu_student` | Студент УрФУ |
| `other_university_student` | Студент другого вуза |
| `student_parent` | Родитель студента |
| `university_employee` | Работник вуза |
| `other` | Прочее |

### 3.2. Institutes

The institute buttons are taken from a configurable list and are shown only to UrFU students and university employees (FLOWS 2). Participants with any other status are not asked for an institute. The list for testing: `ИРИТ-РТФ`, `ИнЭУ`, `ГУК`. It is replaced by the full list later.

### 3.3. Circle statuses (`circles.status`)

| Value | Label |
|---|---|
| 0 | Ожидает автопроверки |
| 1 | Ожидает проверки администратором |
| 2 | Одобрен |
| 2 and `is_buffered` | Одобрен, ожидает добавления в рассылку |
| 3 | Отклонён |

### 3.4. Rejection reasons (`circles.rejection_reason`)

| Value | Label |
|---|---|
| `profanity` | нецензурная лексика |
| `shocking_content` | шокирующий контент |
| `advertising` | реклама |
| `other` | иная причина |

### 3.5. Captcha emoji names

| Emoji | Name | Emoji | Name |
|---|---|---|---|
| ❤️ | Сердце | 🍎 | Яблоко |
| ⚡ | Молния | 🧊 | Лёд |
| 🦴 | Кость | ⭐ | Звезда |
| 👁 | Глаз | 🔥 | Огонь |
| 🦷 | Зуб | ⚽ | Мяч |
| 🦊 | Лиса | 🎲 | Кубик |
| 🐷 | Свинья | 💿 | Диск |
| 🐭 | Мышь | 📕 | Книга |
| 🐥 | Цыплёнок | ✏ | Карандаш |
| 🍉 | Арбуз | 🧻 | Туалетная бумага |

## 4. Registration

| Key | Text |
|---|---|
| `start.welcome` | `🎉 Привет! Это бот новогодних поздравлений УрФУ.\nТы отправляешь один видеокружок с поздравлением, а в новогоднюю ночь получаешь кружки от двух других участников.\nСначала нужно пройти короткую проверку.` |
| `captcha.question` | `🔎 Нажми на {kind}: «{name}»` |
| `captcha.kind` | `эмодзи` or `иконку`, chosen randomly |
| `captcha.wrong` | `❗ Неверно. Осталось попыток: {left}. Попробуй ещё раз.` |
| `captcha.failed` | `🚫 Проверка не пройдена. Доступ к боту закрыт.` |
| `captcha.passed` | `✅ Проверка пройдена.` |
| `consent.text` | `📄 Чтобы продолжить, прочитай документы и прими их.\nПолитика конфиденциальности: {privacy_url}\nПользовательское соглашение: {terms_url}` |
| `consent.button` | `Принять` |
| `status.question` | `👤 Кем ты являешься?` |
| `institute.question` | `🏛 Выбери свой институт.` |
| `timezone.question` | `🌐 Укажи свой часовой пояс: число часов относительно UTC.\nНапример, для Екатеринбурга это 5, для Москвы — 3.` |
| `timezone.invalid` | `❗ Нужно целое число от -12 до 14. Попробуй ещё раз.` |
| `registration.done` | `✅ Регистрация завершена.` |

- The captcha question is built from `captcha.question`, with `{name}` from section 3.5. The four buttons show the emoji themselves.
- The status buttons use the labels from section 3.1.
- `{privacy_url}` and `{terms_url}` are configuration values.

## 5. Circle submission

| Key | Text |
|---|---|
| `circle.ask` | `🎥 Отправь кружок с новогодним поздравлением.\nДлительность — от 3 до 30 секунд.` |
| `circle.wrong_type` | `❗ Отправь именно кружок: видеосообщение, записанное круглой кнопкой в Telegram.` |
| `circle.duration_invalid` | `❗ Кружок должен длиться от 3 до 30 секунд. Запиши другой.` |
| `circle.queued` | `✅ Кружок получен и поставлен в очередь на проверку.\nСтатус можно посмотреть в /menu.` |
| `circle.in_progress` | `⏳ Предыдущий кружок ещё проверяется. Статус можно посмотреть в /menu.` |
| `new.unavailable` | `⏳ Новый кружок можно отправить после того, как закончится проверка текущего.` |
| `new.ask` | `🎥 Отправь новый кружок. Он заменит предыдущий.` |
| `new.no_circle` | `🎥 У тебя ещё нет кружка. Просто отправь его сообщением.` |
| `intake.closed` | `⛔ В данный момент получение новых кружков приостановлено! Следите за ситуацией в нашем канале ({channel_url}) и повторите попытку позже.` |
| `unknown.message` | `❓ Не понял сообщение. Доступные команды: /menu, /new.` |

`{channel_url}` is a configuration value.

## 6. Moderation results

| Key | Text |
|---|---|
| `moderation.auto_rejected` | `❌ Кружок отклонён.\n📌 Причина: {reason}\n⚠ Осталось попыток автопроверки: {auto_left}.\nПодумай и отправь новый кружок командой /new.` |
| `moderation.manual_rejected` | `❌ Кружок отклонён администратором.\n📌 Причина: {reason}\n⚠ Это твой единственный повтор: при следующем отказе доступ будет закрыт.\nПодумай и отправь новый кружок командой /new.` |
| `moderation.approved` | `✅ Кружок одобрен.` |
| `buffer.committed` | `✅ Твой кружок добавлен в новогоднюю рассылку.` |
| `buffer.rejected` | `❌ Кружок отклонён.\n📌 Причина: иная причина` |
| `ban.auto_limit` | `🚫 Попытки автопроверки закончились. Доступ к боту закрыт.` |
| `ban.manual_limit` | `🚫 Кружок отклонён повторно.\n📌 Причина: {reason}\nДоступ к боту закрыт.` |

- `{reason}` uses the labels from section 3.4.
- A participant banned by an administrator with `/ban` receives no message. After a ban, messages from the participant are ignored (FLOWS 1).

## 7. Participant commands

### 7.1. Telegram command menu

| Command | Description |
|---|---|
| `/start` | Регистрация |
| `/menu` | Информация о тебе и твоём кружке |
| `/new` | Отправить новый кружок |

Administrator commands are not shown in the menu.

### 7.2. `/menu` and `/about HID`

```
⭐ Профиль
📆 Дата регистрации: {registered_at}
👤 Статус: {status}
🏛 Институт: {institute}
🌐 Часовой пояс: {timezone}
🎥 Кружок
🆔 ID: {cir_id}
📍 Статус: {circle_status}
⏱ Длительность: {duration} с
📆 Отправлен: {sent_at}
❗ Причина отказа: {reason}
```

- The line with the institute is shown only when the participant has an institute.
- The line with the rejection reason is shown only for status 3.
- If the participant has not sent a circle, the circle block is replaced by one line: `🎥 Кружок: не отправлен`.
- `/about HID` prints the same text for the participant with that HID.

## 8. New Year mailing

For every circle delivered, the bot sends two messages in a row:

1. Text: `🎉 Поздравление от {full_name}`
2. The circle of that participant.

There is no link to the sender's profile.

## 9. Administrator texts

### 9.1. Moderation buttons

Under the circle in the administrators' chat: `✅`, `❌`.

After `❌` the buttons are replaced with:

| Button | Meaning |
|---|---|
| `Отмена, принять` | Cancel the rejection and approve |
| `Содержит нецензурную лексику` | Reason `profanity` |
| `Содержит шокирующий контент` | Reason `shocking_content` |
| `Реклама` | Reason `advertising` |
| `Иная причина` | Reason `other` |

### 9.2. Intake notifications

| Key | Text |
|---|---|
| `intake.admin_closed` | `🔒 Приём кружков закрыт\n🕒 Время: {time} ЕКБ\n📌 Причина: {reason}` |
| `intake.admin_reopened` | `🔓 Приём кружков открыт\n🕒 Время: {time} ЕКБ\n📌 Причина закрытия устранена: {reason}` |
| `close.on` | `🔒 Приём кружков закрыт вручную.` |
| `close.off` | `🔓 Ручное закрытие приёма снято.` |

Closing reasons:

| Reason | Text |
|---|---|
| scheduled | `закрытие по расписанию` |
| manual | `закрыт вручную командой /close` |
| environment flag | `закрыт флагом в настройках` |
| CPU | `загрузка CPU выше 90% дольше 3 минут (сейчас {value}%)` |
| disk | `свободного места на диске меньше 1 ГБ (сейчас {value} ГБ)` |
| queue | `в очереди автопроверки больше 1000 участников (сейчас {value})` |

### 9.3. Command responses

| Key | Text |
|---|---|
| `look.not_found` | `❗ Кружок {cir_id} не найден.` |
| `ban.done` | `🚫 Участник {hid} заблокирован.` |
| `ban.not_found` | `❗ Участник {hid} не найден.` |
| `accept.done` | `✅ Статус кружка {cir_id} изменён на 2.` |
| `reject.done` | `✅ Статус кружка {cir_id} изменён на 3.` |
| `status.not_found` | `❗ Кружок {cir_id} не найден.` |
| `send.ask` | `📣 Отправь сообщение для рассылки. Оно уйдёт всем пользователям в точно таком же виде.` |
| `send.started` | `⏳ Рассылка запущена.` |
| `send.done` | `✅ Рассылка завершена.\n📤 Отправлено: {sent}\n📥 Получили: {received}\n🕒 Начало: {started} ЕКБ\n🕒 Конец: {finished} ЕКБ` |

`/stats`:

```
📊 Статистика
👥 Всего пользователей: {total_users}
📝 Зарегистрировано: {registered}
🎥 Кружков всего: {circles_total}
📆 Отправлено сегодня: {circles_today}
✅ Одобрено: {approved}
❌ Отклонено вручную: {rejected_manual}
🤖 Отклонено автоматически: {rejected_auto}
```
