# INFRA

Infrastructure of Urfu27bot: server, runtime, services, resource limits, logging and backups. This spec is public. It never contains secrets, credentials, addresses or the names of environment variables.

## 1. Security rules for this spec and the repository

- All secrets and environment-specific values are read from environment variables loaded from `.env` (RULES 5). This spec does not list them.
- The `.env` file on the server is readable only by the account that runs the bot.
- PostgreSQL accepts connections only from the same machine.
- The bot process runs under an unprivileged account, not under root.
- Logs, backups and temporary files never contain secrets and are excluded from git.

## 2. Servers

### 2.1. Production

- VPS with Ubuntu 24.04, 1 vCPU, 2 GB RAM, about 7 GB of free disk. At least 10 GB more is added later.
- Python 3.13.3 is installed next to the system Python (the system interpreter is not replaced) and used through a virtual environment in the project.
- System packages required: PostgreSQL, ffmpeg.

### 2.2. Test

- The test bot is the same code with a different bot token and a separate database.
- It runs locally on the author's PC for a couple of hours at a time.
- Switching between test and production is done manually by changing the values in `.env`.

## 3. Runtime

- The bot is one long-running Python process with a single entry point `run.py`, the same principle as in LoveLine.
- The bot uses long polling. There is no webhook and no domain is required.
- The process is run and restarted automatically by the system service manager (systemd). Docker is not used.
- Scheduled and background tasks (FLOWS 13) run in the same process on an async scheduler (APScheduler).
- Schedules that depend on a time zone are defined with an explicit time zone. The server time zone must not affect behavior. The intake closure of 25 December 2026, 00:00 Yekaterinburg time, is 19:00 UTC on 24 December 2026.

## 4. Database

- PostgreSQL runs on the same VPS. The bot uses async SQLAlchemy with the asyncpg driver.
- The bot connects with a dedicated database role that has rights only on its own database.
- Schema changes go through Alembic migrations (RULES 7).

## 5. Speech recognition

### 5.1. Pipeline

1. The bot downloads the circle by `file_id` into a temporary directory excluded from git.
2. ffmpeg extracts the audio as 16 kHz mono.
3. The recognition engine converts it to text.
4. The temporary files are deleted right after processing.

### 5.2. Engine

- Primary engine: GigaAM v3 (Russian, MIT license) quantized to INT8 and run with ONNX Runtime on CPU. The model files are downloaded on the server and are not stored in the repository.
- Fallback engine: Vosk small Russian model (Apache 2.0), used if the primary engine does not fit the server's RAM or time budget.
- Before the choice is final, the agent measures processing time and memory for a 30-second circle on the production server and reports the result to the user.

### 5.3. Single worker and CPU budget

- Recognition runs in one worker.
- The worker is limited so that its own sustained CPU use stays below the intake closing threshold (FLOWS 9.1), otherwise the queue itself would close intake.
- Above 95 percent total CPU load the worker is throttled (FLOWS 5).

### 5.4. External API (overflow)

- Used only when the automatic moderation queue exceeds 50 participants (PRODUCT 4.1).
- Provider: Groq Whisper (large-v3 or large-v3-turbo) on the free plan. The free plan limits are about 20 requests per minute, 2000 requests per day, 7200 audio seconds per hour, 28800 audio seconds per day and 25 MB per file. The bot must stay within them.
- The API key is read from the environment.
- If the API does not respond, the queue is processed locally (PRODUCT 4.1).
- The availability of the API from the production server is verified before relying on it.

### 5.5. Forbidden-word lists

- Two lists: profanity and advertising (FLOWS 5).
- They are stored on the server in files excluded from git and are never committed.

## 6. Monitoring

- Inside the bot process, using the system metrics library (psutil), the monitor reads CPU load, free disk space on the disk with the database, and the length of the automatic moderation queue.
- Thresholds and the actions on exceeding them are defined in FLOWS 9.
- The check interval is a configuration value.
- No external monitoring is used.

## 7. Logging

- Log file: `~/logs.txt` in the home directory of the account that runs the bot.
- Rotation is mandatory: the total size of the log file and its rotated copies must not exceed 10 MB, and the oldest data is removed first.
- What may be logged and what may not is defined in RULES 8. The rejected circle log format is in DATA 7.1.

## 8. Backups

- The database is dumped once a week with the standard PostgreSQL dump tool, together with the triples CSV file once it exists.
- The last 4 weekly copies are kept; older ones are deleted.
- Backups are stored in a directory outside the repository.
- Copying a backup off the server is done manually by the author.

## 9. Sizing

Expected scale: from about 50 to 15000 participants (PRODUCT 10).

- Disk: the database holds only text and identifiers, tens of megabytes at most. Circles are not stored, only `file_id`. Temporary files are removed after processing. The logs are capped at 10 MB. Free-space closing threshold: FLOWS 9.1.
- RAM: the bot, PostgreSQL and the recognition engine have to fit in 2 GB together.
- CPU: the main load is recognition on a single core. The worker limit in section 5.3 and the overflow API in section 5.4 protect the server during peaks.
- Mailing: at most 8 messages per second (FLOWS 12), which keeps a New Year mailing of up to 15000 participants within a few hours.
