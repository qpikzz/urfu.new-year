# FLOWS

Behavior of Urfu27bot: scenarios, rules and commands. Product context is in PRODUCT, data in DATA. Message texts and keyboards are defined in the messages spec; this file defines when and why they are sent.

## 1. General rules

- Every update first resolves the participant by HID. Messages from a banned participant (`users.is_banned`) are ignored completely.
- Administrators are identified by the HIDs listed in the environment configuration. Admin commands from anyone else are ignored.
- The administrators' chat is the chat where the bot sends circles for manual moderation. It also receives system notifications (section 9).
- The "intake" is the acceptance of new circles. When intake is closed, any attempt to send a circle (first circle or via `/new`) gets the closed-intake message (section 9.4). Registration, `/menu` and all other commands keep working.
- A participant row is created at `/start`, so a ban can be recorded even before registration is finished.

## 2. Registration

Order of steps for `/start`:

1. Captcha (section 3).
2. Acceptance of the Privacy Policy and the User Agreement. The participant must accept both to continue.
3. The bot saves `full_name` and `username` (`0` if absent) automatically and sets `registered_at`.
4. Status question (six statuses, DATA 6.1).
5. Institute question, only for the statuses `urfu_student` and `university_employee`. For all other statuses nothing is asked.
6. Time zone question: the participant must enter an integer number of hours of the offset from UTC, in the range -12 to +14. Any other input is rejected with a request to enter an integer.
7. The bot asks for the circle (section 4), or sends the closed-intake message if intake is closed.

Rules:

- Registration resumes from the same step: if the participant interrupts the dialog, the next `/start` or message continues from the step where it stopped.
- If registration is already complete, `/start` replies as `/menu` does.
- Registration stays open after 25 December 2026; only intake closes.

## 3. Captcha

- The bot asks a question of the form "Press the emoji X" or "Press the icon X" and shows 4 buttons, one of which is correct.
- The emoji set is: ❤️ ⚡ 🦴 👁 🦷 🦊 🐷 🐭 🐥 🍉 🍎 🧊 ⭐ 🔥 ⚽ 🎲 💿 📕 ✏ 🧻
- A wrong answer gives 2 more attempts. After the third wrong answer the participant is banned.

## 4. Circle submission

Accepted only as a Telegram video note (circle).

- Valid duration: from 3 to 30 seconds inclusive. Other durations are rejected with a message stating the allowed range; the attempt is not counted against any limit.
- Any other content type (text, regular video, voice, sticker and so on) gets a reply asking to send exactly a circle.
- A first circle is accepted when `users.cir_id` is empty.
- While the latest circle is being processed (status 0 or 1), new circles are not accepted; the bot points to `/menu`.
- On acceptance the bot creates a row in `circles` with status 0, stores `file_id`, `sent_at`, `duration` and `owner_hid`, sets `users.cir_id` to the new circle and puts the circle in the automatic moderation queue.

### 4.1. `/new`

- Available only when the latest circle has status 2 or 3.
- The bot asks for a new circle. The new circle is created as in section 4 with status 0 and `users.cir_id` is overwritten. The old circle remains in the database.
- If the previous circle was manually rejected (status 3 with `rejected_by` set to manual), sending the new circle increments `users.resubmissions_used`.
- `/new` itself has no usage limit; limits are enforced through rejections (section 7).

## 5. Automatic moderation

- Queue: first in, first out; the oldest circles are processed first.
- Processing: extract the audio, convert it to text, check the text against the forbidden-word lists.
- The forbidden-word lists are kept in files excluded from git. There are two categories: profanity and advertising.
- Recognition uses the own CPU algorithm. When the queue exceeds 50 participants, part of the queue is moved to an external API. If the load is high and the API does not respond, the queue is processed locally; automatic checking may take up to a week.
- When CPU load exceeds 95 percent, the system artificially limits its load (throttles processing) until the load decreases.
- Frame-based checking is a later stage and is not part of the MVP.

Outcome:

- Nothing forbidden found: status becomes 1 and the circle goes to manual moderation.
- Forbidden words found: status becomes 3, `rejection_reason` is `profanity` or `advertising` depending on what was found, `rejected_by` is automatic. The circle never reaches administrators. `users.auto_attempts_used` is incremented. The participant receives the reason and a warning about the remaining limits and a suggestion to think and send a new circle with `/new`. The rejection is written to the log (HID, Circle ID, transcript).
- When `auto_attempts_used` reaches 3, the participant is banned instead of getting the `/new` suggestion.

While a circle is processed, `/menu` shows its status and duration.

## 6. Manual moderation

- Every circle with status 1 is sent to the administrators' chat with the buttons ✅ and ❌.
- Several administrators may be present. Only the first press counts. There is no timeout.
- After the decision, the message with the circle is deleted from the administrators' chat.
- ✅: status becomes 2 and the participant is notified. After registration closes, approvals go through the buffer (section 10).
- ❌: the bot offers the options "Cancel, accept", "Contains profanity", "Contains shocking content", "Advertising", "Other reason".
  - "Cancel, accept": the rejection is cancelled and the circle is approved as with ✅.
  - Any other option: status becomes 3, `rejection_reason` is set (`profanity`, `shocking_content`, `advertising`, `other`), `rejected_by` is manual. The participant receives the reason and a warning about the remaining limits.
- On a manual rejection, if `users.resubmissions_used` is already 1 (the participant has already used the one repeated submission), the participant is banned instead of getting the `/new` suggestion.

## 7. Limits and ban

- Automatic moderation: 3 attempts. Each automatic rejection consumes one; the third rejection bans.
- Manual moderation: one repeated submission after a manual rejection. A second manual rejection bans.
- Counters are stored per participant (`auto_attempts_used`, `resubmissions_used`); limit values are constants.
- A ban sets `users.is_banned`. A banned participant's messages are ignored.
- Administrators can ban manually with `/ban`.

## 8. User command `/menu`

A short message about the participant: status, institute if present, and information about the latest circle (status, duration, send date, rejection reason if rejected). Available at any time after registration starts. Texts are in the messages spec.

## 9. Intake control

### 9.1. Closing reasons

Intake is closed while at least one reason is active:

- Scheduled: from 00:00 Yekaterinburg time on 25 December 2026.
- Manual: the `/close` command, or the environment flag.
- Automatic: CPU load above 90 percent for more than 3 minutes; less than 1 GB of free disk space; more than 1000 participants in the automatic moderation queue.

### 9.2. Manual control

- `/close` (administrators only) toggles the manual closure: the first call closes intake, the next call reopens it. The state is stored in the database (DATA 5).
- The environment flag closes intake from start-up when it is set; it is read at start-up. Both manual mechanisms are part of the MVP.

### 9.3. Automatic control

- A monitoring task checks CPU load, free disk space and the queue length periodically (interval in configuration).
- When an automatic condition appears, intake is closed. The administrators' chat receives a message with the time, the reason and related details.
- When no automatic condition holds any more, intake is reopened and the administrators' chat receives a message about the recovery time.

### 9.4. Closed-intake message

The participant who tries to send a circle while intake is closed receives: "В данный момент получение новых кружков приостановлено! Следите за ситуацией в нашем канале (ссылка на канал) и повторите попытку позже." The channel link is a configuration value.

## 10. Registration close and the approval buffer

The buffer is active only after the scheduled closure (25 December 2026, 00:00 Yekaterinburg time). Before that, an approval takes effect immediately.

Definitions: the committed set is circles with status 2 that are not buffered. The buffer is circles with status 2 and `is_buffered` set.

Flow after closure:

1. Moderation continues for circles already in the queue.
2. A manual approval puts the circle into the buffer (status 2, `is_buffered` set). The participant is not notified yet.
3. When the size of the committed set plus the buffer is a multiple of 3 and the buffer is not empty, all buffered circles are committed (`is_buffered` cleared) and each participant is notified that the circle is added.
4. The process repeats: buffering continues until the next multiple of 3 is reached.
5. When no circle with status 0 or 1 remains, moderation is finished. Circles still in the buffer (1 or 2) are rejected: status 3, reason `other`, `rejected_by` is manual, and the participants are notified.
6. If the committed set is still not a multiple of 3, the latest circles by `sent_at` are rejected (status 3, reason `other`), at most two, until the count is a multiple of 3.

Example: 1000 committed; the next two approvals are buffered and committed together (1002); then approvals are committed in groups of 3.

Triples are formed once after this point (PRODUCT 7); the trigger for it is outside the MVP.

## 11. Admin commands

- `/look CirID`: sends the circle with that id to the administrator.
- `/ban HID`: bans the participant with that HID.
- `/stats`: project statistics: total users, registered users (registration completed), total circles, circles sent today, approved, rejected manually, rejected automatically. "Today" is counted in Yekaterinburg time.
- `/send`: manual announcement (section 12.1).
- `/accept CirID`: silently sets the status of the circle to 2 in the database.
- `/reject CirID`: sets the status of the circle to 3 with the reason `other`.
- `/about HID`: prints the `/menu` information of the participant with that HID.
- `/close`: toggles the manual closure of intake (section 9.2).

## 12. Mailings

Common rules:

- The mailing rate is at most 8 messages per second.
- A participant who has blocked the bot is not retried.
- Every mailing run is recorded in `mailing` (DATA 4).

### 12.1. Manual announcement (`/send`)

- The bot asks the administrator for the message. The message may be anything: text, picture with caption, sticker and so on.
- After receiving it, the bot sends it to all users in exactly the same form.
- There are no retries.

### 12.2. New Year mailing

- Planned by a background scheduled task, in the same manner as in LoveLine.
- Content: for every participant, the circles of the other two members of the participant's triple, each with the sender's full name and without a link to the profile.
- Recipients: participants whose own circle is committed (status 2, not buffered) and who are in a triple.
- The task runs periodically. On each pass it selects participants whose local time (UTC plus `users.timezone`) has reached 00:00 on 1 January 2027 and whose `greeting_received` is not set, and tries to send.
- On success `greeting_received` is set.
- If the participant has blocked the bot, no further attempts. Any other error: the participant remains eligible and is retried on the next pass.
- Test deliveries run before the real one on a separate test bot.

## 13. Background tasks

- Automatic moderation worker (queue, recognition).
- Resource monitor (CPU, disk, queue length) that controls intake.
- Scheduled closure of intake on 25 December 2026.
- New Year mailing scheduler.
