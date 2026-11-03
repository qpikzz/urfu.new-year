# DATA

Data model of Urfu27bot: database tables, fields, value sets and data kept outside the database. Behavior is defined in PRODUCT and in the flows spec.

## 1. General rules

- Database: PostgreSQL. Schema changes go through Alembic migrations (RULES).
- Only the minimum necessary information is stored in the database.
- Video files are never stored. A circle is stored only as a Telegram `file_id`.
- Recognized speech text is not stored in the database; it appears only in logs (section 6).
- Timestamps are stored in UTC.
- The language of the bot is Russian only, so no language field exists.
- The HID encoding and decoding function (a reversible transformation of the Telegram user ID) is written by the author and supplied as a separate module. Agents use it as an external dependency and never implement or modify it.
- Administrator HIDs are not stored in the database; they are defined in the environment configuration.

## 2. Table `users`

| Field | Description |
|---|---|
| `hid` | Hidden transformed Telegram ID. Unique identifier of the participant |
| `full_name` | Full name taken from Telegram |
| `username` | Telegram username, or `0` if the user has none |
| `status` | Participant status (section 5.1) |
| `institute` | Institute; filled for students and university employees, empty otherwise |
| `timezone` | Offset from UTC in whole hours, an integer |
| `cir_id` | `id` of the participant's latest circle in `circles`; empty until the first circle is sent |
| `registered_at` | Registration date and time |
| `is_banned` | Ban flag |
| `auto_attempts_used` | Counter of automatic moderation attempts used |
| `resubmissions_used` | Counter of repeated circle submissions after a rejection |

- The time zone is entered by the participant as an exact integer. Zones with half-hour offsets are not supported.
- Only counters are stored in the database. The limit values (3 automatic moderation attempts, 1 repeated submission after a rejection) are constants defined in the specs and the configuration, not table data.

## 3. Table `circles`

| Field | Description |
|---|---|
| `id` | Unique integer identifier: 1, 2, 3, ... |
| `owner_hid` | HID of the participant who sent the circle (reference to `users.hid`) |
| `file_id` | Telegram `file_id` of the circle |
| `sent_at` | Date and time the circle was sent |
| `duration` | Duration of the circle in seconds |
| `status` | Circle status (section 5.2) |
| `rejection_reason` | Reason of rejection; empty unless the status is 3 (section 5.3) |

- A participant may have more than one row in `circles` (a repeated submission after a rejection). `users.cir_id` always points to the latest one.

## 4. Table `mailing`

One row per mailing run, not per recipient.

| Field | Description |
|---|---|
| `id` | Unique integer identifier |
| `started_at` | When the mailing started |
| `finished_at` | When the mailing finished |
| `sent_count` | Number of messages or participants processed (sent) |
| `received_count` | Number of participants who received the mailing |
| `received_hids` | List of HIDs of the participants who received the mailing |

## 5. Value sets

### 5.1. Participant status (`users.status`)

- `applicant`
- `urfu_student`
- `other_university_student`
- `student_parent`
- `university_employee`
- `other`

### 5.2. Circle status (`circles.status`)

| Value | Meaning |
|---|---|
| 0 | Awaiting automatic moderation |
| 1 | Approved automatically |
| 2 | Approved manually |
| 3 | Rejected |

### 5.3. Rejection reason (`circles.rejection_reason`)

- `profanity`: contains profanity.
- `shocking_content`: contains shocking content.
- `advertising`: advertising.
- `other`: other reason (also used for surplus circles rejected after registration closes, see PRODUCT 6).

The reason is stored in the database and shown to the participant. The mapping of automatic moderation outcomes to reasons is defined in the flows spec.

## 6. Data outside the database

### 6.1. Rejected circle log

- The automatic moderation history is kept only in logs, and only for rejected circles.
- Format of a record: HID, Circle ID, transcript (text only).
- Logs follow the logging rules in RULES.

### 6.2. Triples file

- Triples (PRODUCT 7) are stored separately in a CSV file: each row contains the 3 HIDs of one triple.
- The file contains personal identifiers and must never be committed to the repository (RULES 5).
- Its location and exact format are defined later.

### 6.3. Environment configuration

- Administrator HIDs and other secrets are read from the environment configuration (RULES 5).