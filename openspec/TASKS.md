# TASKS: 7-day MVP implementation plan

The code is written by an agent working under RULES. Tasks of the author are marked **[Nikita]**. The parentheses after a task name list the spec sections the task is based on.

## Rules for using this file

- The file is **read-only**. The agent never edits it and never marks completion in it. Progress is kept only in the files of `openspec/tasks/` (RULES 4).
- Task numbers (1.1, 2.3 and so on) are used only for references. **File names never contain task numbers.**
- A task file is named `openspec/tasks/YYYY-MM-DD-<name>.md`, where `<name>` is the value of the field "Name" of the task. Example: task 1.1 gives `openspec/tasks/2026-11-05-project-setup.md`.
- Every task ships with tests for the new logic and handlers (RULES 9).
- Tasks that create or change models, tables or migrations require the user's permission before the change is made (RULES 3).
- Tasks marked **[Nikita]** are not done by the agent. If the agent needs their result and it is missing, it asks the user (RULES 2).

## Order and logic

1. Skeleton, configuration and logging first, so everything else is built in one structure.
2. Then the data layer and the texts, because every flow depends on them.
3. Then registration, circle intake and moderation, the riskiest part.
4. Then admin commands, intake control and resource monitoring.
5. The last day: verification on the test bot, fixes, deployment and launch.

## Parallel tasks of the author

- **[Nikita]** Before Day 1 ends: bot tokens (test and production), the administrators' chat, the administrators' HIDs, the HID encode/decode module (DATA 1).
- **[Nikita]** Before Day 3: decide the employee status question (a participant from another university is asked for a UrFU institute; see "Open decisions").
- **[Nikita]** Before Day 4: the forbidden-word lists, profanity and advertising, as files outside git (INFRA 5.5).
- **[Nikita]** Before Day 6: decide how the CPU closing threshold and the recognition worker limit interact (see "Open decisions"); prepare the VPS (task 6.4).
- **[Nikita]** Before launch (Day 7): links to the Privacy Policy and the User Agreement, the channel link, the full institute list.

---

## Day 1. Foundation

- **1.1 Project.** Name: `project-setup`. Repository structure with the single entry point `run.py`, one handler file per command, a keyboards module, a content module for texts, Python 3.13.3 virtual environment, minimal dependencies, `.gitignore` that covers `.env`, logs, temporary files, models, forbidden-word files, backups and the triples file, `.env.example` without values (RULES 5, 6; INFRA 1, 3).
- **1.2 Configuration and logging.** Name: `config-logging`. Loading of the environment configuration, log file `~/logs.txt` with rotation and a 10 MB total cap, logging only HID and never the Telegram user ID or secrets (RULES 5, 8; INFRA 7).
- **1.3 HID integration.** Name: `hid-integration`. Use of the author's HID module as an external dependency through a small interface; the agent does not implement or change the algorithm (DATA 1).
- **1.4 [Nikita] Prerequisites.** Create the bots and tokens, the administrators' chat, provide administrator HIDs and the HID module.

**Done when:** the project starts with a test token, answers nothing yet, writes to the log file, and no secret is in the repository.

## Day 2. Data layer and texts

- **2.1 Models.** Name: `db-models`. Tables `users`, `circles`, `mailing`, `settings` with all fields and value sets (DATA 2-6). Requires the user's permission (RULES 3).
- **2.2 Migrations.** Name: `db-migrations`. Alembic setup and the initial migration (RULES 7; INFRA 4). Requires the user's permission.
- **2.3 Requests.** Name: `db-requests`. Request layer in separate files: users, circles, counters, settings, statistics queries (DATA 2-5; FLOWS 11).
- **2.4 Texts.** Name: `texts-module`. All messages, labels and keyboards from MESSAGES as one module, including the emoji formatting rules (MESSAGES 1-9).
- **2.5 Test base.** Name: `test-base`. pytest setup in a separate tests folder, test database fixture, bot and update mocks (RULES 9).

**Done when:** the schema is created by migration, requests work against a test database, texts are importable and tests run.

## Day 3. Registration

- **3.1 Start flow.** Name: `start-flow`. `/start`, creation of the user row, resuming from the interrupted step, reply as `/menu` if registration is complete (FLOWS 2).
- **3.2 Captcha.** Name: `captcha`. Emoji question with 4 buttons, 2 extra attempts, ban after the third mistake (FLOWS 3; MESSAGES 3.5, 4).
- **3.3 Consent.** Name: `consent`. Privacy Policy and User Agreement links from the configuration and the accept button (FLOWS 2; MESSAGES 4).
- **3.4 Profile steps.** Name: `profile-steps`. Status buttons, institute buttons for UrFU students and employees only, time zone as an integer from -12 to 14 (FLOWS 2; MESSAGES 3.1, 3.2, 4).
- **3.5 Menu.** Name: `menu-command`. `/menu` with status, institute, time zone and circle information (FLOWS 8; MESSAGES 7.2).
- **3.6 Banned and ignored.** Name: `ban-middleware`. Ignoring all messages from banned participants and silent handling of unavailable commands (FLOWS 1).

**Done when:** a new participant passes captcha, consent and all profile steps and sees a correct `/menu`; an interrupted registration resumes.

## Day 4. Circles and automatic moderation

- **4.1 Circle intake.** Name: `circle-intake`. Accepting video notes only, duration from 3 to 30 seconds, replies to other content, a row in `circles`, `cir_id`, queue entry, refusal while the previous circle is in progress (FLOWS 4; MESSAGES 5).
- **4.2 New circle.** Name: `new-command`. `/new` available only for statuses 2 and 3, replacing `cir_id`, `resubmissions_used` after a manual rejection (FLOWS 4.1).
- **4.3 Recognition engine.** Name: `speech-recognition`. Download by `file_id`, audio extraction with ffmpeg, GigaAM v3 INT8 on ONNX Runtime, temporary files removed after processing; Vosk small as the fallback (INFRA 5.1, 5.2).
- **4.4 Forbidden words.** Name: `forbidden-words`. Loading the two lists from files outside git, checking recognized text, deciding profanity or advertising (FLOWS 5; INFRA 5.5).
- **4.5 Automatic moderation.** Name: `auto-moderation`. First-in-first-out queue worker, outcomes, automatic rejection with reason and counters, the rejection log in the format HID, Circle ID, transcript, ban at the third rejection (FLOWS 5, 7; DATA 7.1; MESSAGES 6).
- **4.6 [Nikita] Benchmark.** Run the benchmark script on the VPS for a 30-second circle and report time and memory.

**Done when:** a circle goes through the queue, a clean one gets status 1, a forbidden one is rejected with the right reason and the counter grows, three rejections ban.

## Day 5. Manual moderation and admin commands

- **5.1 Manual moderation.** Name: `manual-moderation`. Sending circles with status 1 to the administrators' chat with ✅ and ❌, first press wins, reasons keyboard including "Cancel, accept", deleting the message after the decision, setting status 2 or 3 and the reason (FLOWS 6; MESSAGES 9.1).
- **5.2 Limits and bans.** Name: `limits-bans`. Manual rejection warnings, the one repeated submission, ban at the second manual rejection, all notifications (FLOWS 7; MESSAGES 6).
- **5.3 Admin check.** Name: `admin-access`. Administrator identification by HID from the configuration, no reaction for everyone else (FLOWS 1).
- **5.4 Admin commands.** Name: `admin-commands`. `/look`, `/ban`, `/accept`, `/reject`, `/about` (FLOWS 11; MESSAGES 9.3).
- **5.5 Statistics.** Name: `stats-command`. `/stats` with all counters and "today" in Yekaterinburg time (FLOWS 11; MESSAGES 9.3).
- **5.6 Announcement.** Name: `announcement-send`. `/send` for any content type, copying the message to all users at no more than 8 messages per second, no retries, a row in `mailing` (FLOWS 12.1; DATA 4).

**Done when:** a circle passes automatic moderation, an administrator approves or rejects it, the participant is notified, limits and bans work, all admin commands answer correctly.

## Day 6. Intake control, resource monitoring, deployment

- **6.1 Intake control.** Name: `intake-control`. Closing reasons (manual `/close` toggle, environment flag, automatic), stored state, closed-intake message, notifications to the administrators' chat (FLOWS 9; MESSAGES 5, 9.2; DATA 5).
- **6.2 Resource monitor.** Name: `resource-monitor`. Periodic check of CPU, free disk space and queue length, closing and reopening intake, throttling above 95 percent CPU, the worker limit (FLOWS 5, 9.3; INFRA 5.3, 6).
- **6.3 Backups.** Name: `backup-script`. Weekly database dump script with 4 copies kept and the triples file when it exists (INFRA 8).
- **6.4 [Nikita] Server.** Prepare the VPS: Python 3.13.3, PostgreSQL, ffmpeg, service unit, `.env`, model download, forbidden-word files, weekly schedule for the backup script (INFRA 2, 3, 8).
- **6.5 Overflow API.** Name: `overflow-api`. Groq Whisper for queues above 50 participants within the free limits, fallback to the local queue (INFRA 5.4). Can be postponed (see priorities).

**Done when:** intake closes and opens by every mechanism and the administrators' chat is notified; the bot runs on the VPS as a service and restarts after failures.

## Day 7. Verification and launch

- **7.1 Test coverage.** Name: `test-coverage`. Fill the gaps in tests for logic and handlers (RULES 9).
- **7.2 End-to-end check.** Name: `e2e-check`. Scenarios on the test bot: registration, valid and invalid circles, automatic rejection, manual approval and rejection, limits and bans, `/new`, intake closing, `/send`, resume of interrupted registration.
- **7.3 Fixes.** Name: `final-fixes`. Fixes after verification and a clean start.
- **7.4 [Nikita] Launch.** Final links in the configuration, production run, check in the administrators' chat, announcement.

**Done when:** the full user scenario works on the VPS without errors and the author has checked it end to end.

---

## Priorities when time is short

1. **Mandatory:** registration with captcha, consent, status, institute and time zone; circle intake; automatic moderation; manual moderation; limits and bans; `/menu`; `/new`; `/look`, `/ban`, `/accept`, `/reject`, `/about`; manual intake closing (`/close` and the environment flag).
2. **Important:** resource monitor with automatic closing; `/stats`; `/send`; logs with rotation; backups.
3. **Can be cut:** overflow API; Vosk fallback; throttling details; the benchmark report format.

## Outside the 7 days (before 1 January)

These are required for the real event but are not part of the MVP (PRODUCT 9). They are planned as separate tasks.

- Scheduled intake closure on 25 December 2026 and the approval buffer (FLOWS 10; DATA 3).
- Triple formation and the triples CSV file (PRODUCT 7; DATA 7.2).
- New Year mailing scheduler with `greeting_received` and test deliveries on a separate bot (FLOWS 12.2; MESSAGES 8).
- Medium and maximum plans and frame-based moderation (PRODUCT 8, 9).

## Open decisions of the author

- **Employee status.** The status "university employee" covers any university, but the institute is asked only for UrFU employees. Either split the status into "UrFU employee" and "other university employee" (seven statuses, DATA 6.1 and the labels in MESSAGES 3.1 change) or accept that every employee sees the UrFU institute list.
- **CPU threshold and the worker.** Closing intake above 90 percent CPU for 3 minutes can be triggered by the recognition worker alone on a single core. INFRA 5.3 limits the worker below the threshold; confirm or change the rule.
