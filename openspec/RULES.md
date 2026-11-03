# RULES

Rules for AI agents (opencode, Copilot) working on the Urfu27bot repository.
These rules are mandatory and take precedence over any agent default behavior.

## 1. Language

- Specs, code, identifiers, code comments, log messages, commit-message suggestions and short task names: **English**.
- All user-facing bot texts (messages, buttons, notifications): **Russian**.
- Task memory files in `openspec/tasks/` are written in **Russian** (see section 4).

## 2. Specs

- Specs live in `openspec/`. Agents must **never** modify any spec file (`RULES.md`, `PRODUCT.md`, and all other files in `openspec/specs/`).
- The only place inside `openspec/` where agents may write is `openspec/tasks/`.
- If a spec is contradictory, incomplete or ambiguous, the agent stops and asks the user. The agent does not guess and does not silently choose an interpretation.
- Any other question that arises during work is also asked to the user, all at once, before continuing.

## 3. Forbidden without explicit user permission

- Changing any spec file.
- Any git write operation: `add`, `commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `checkout`, `branch`, `tag`, `stash`, etc. Read-only commands (`status`, `diff`, `log`, `show`) are allowed.
- Changing the database schema (models, tables, columns, constraints, indexes) and creating or editing Alembic migrations.

Permission applies to one specific change and does not carry over to later changes.

## 4. Task memory

For every task the agent keeps a file in `openspec/tasks/`. This is the only place inside `openspec/` where the agent may write. Creating any other `tasks/` folder (including in the project root) is forbidden.

### 4.1. File name

Format: `openspec/tasks/YYYY-MM-DD-short-description.md`

- The date is the current date obtained by a terminal command. The date must never be invented.
- The short description is in English, lowercase, words separated by hyphens.
- Correct: `openspec/tasks/2026-11-03-project-setup.md`.
- Incorrect: `openspec/tasks/project-setup.md` (no date), `tasks/2026-11-03-project-setup.md` (folder outside `openspec/`).

### 4.2. File content (in Russian)

- **Описание:** the essence of the task and references to spec sections.
- **План:** execution steps.
- **TODO:** remaining and postponed items.
- **Действия:** a brief description of the completed actions.

### 4.3. Working with task files

- Before starting, the agent inspects `openspec/tasks/`. If a file for this task already exists (determined by the task description; the date in the name may differ), the agent updates it and does not create a new one. The date in an existing file name is never changed.
- For minor fixes the agent edits existing files instead of creating small new ones.
- The file is updated during the work: checked plan items, current TODO, list of actions.
- The agent may plan structure and architecture in advance and records the plan in the task file.

## 5. Secrets and public repository

The repository is **fully public**. Secrets must never reach it.

- Every secret and environment-specific value (bot token, admin ids, database credentials, API keys, salts and any other value used to derive `hid`) is read from environment variables loaded from `.env`.
- `.env` is listed in `.gitignore` **before** the first commit. The repository contains only `.env.example` with variable names and empty or placeholder values.
- Whenever the agent adds any sensitive mechanic (external API, user data handling, database access, new credentials), it in the same change: adds the variable to `.env` loading, adds it to `.env.example`, and verifies that `.gitignore` covers every related file.
- The repository must not contain: real user data, database dumps, Telegram `file_id` values of real circles, media files of real users, log files.
- Secrets are never hardcoded, never printed to logs and never included in test fixtures.
- If the agent notices a secret in code or history, it stops and reports it to the user immediately.

## 6. Code quality

- Code must be clean, readable and maintainable. Prefer simple solutions; no speculative abstractions.
- Stack: Python, Aiogram, async SQLAlchemy, PostgreSQL. Code is asynchronous end to end; blocking work (speech recognition, video processing) must not block the event loop.
- Code comments are in English and are written only where the intent is not obvious.
- The agent may add dependencies when needed, keeping the dependency file up to date and avoiding unnecessary packages.
- Architecture and structure are planned in advance in the task file before implementation.

## 7. Database

- The schema is managed with Alembic migrations (a migration is a versioned script that changes the schema step by step, so the live database can evolve without data loss).
- Every schema change goes through a migration. Changes and migrations require user permission (section 3).
- Parameters that govern behavior (such as moderation attempts and resubmission limits) are stored in the database, as defined in the specs.

## 8. Logging

- Logs are written to a separate log file, not only to the console. The log file is git-ignored.
- Never log the Telegram user ID.
- Allowed in logs: `cid`, recognized speech text, circle id and similar technical identifiers.
- Never log secrets, tokens or credentials.

## 9. Testing and release

- Tests are mandatory and use pytest. They cover business logic and bot handlers.
- New functionality ships with tests. Existing tests must pass before a task is considered complete.
- Before every release the agent verifies that the project starts, the main flows work and there are no known bugs, and reports the result to the user.