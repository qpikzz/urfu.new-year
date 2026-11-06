from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from app.config import Config, ConfigError, load_config
from app.logging_setup import (
    LOG_BACKUP_COUNT,
    LOG_MAX_TOTAL_BYTES,
    REDACTED,
    SecretRedactionFilter,
    setup_logging,
)

FAKE_TOKEN = "123456:fake_token"
FAKE_DATABASE_URL = "postgresql+asyncpg://user:password@localhost/db"
FAKE_GROQ_KEY = "gsk_fake_key"
ENV_NAMES = (
    "BOT_TOKEN",
    "ADMIN_CHAT_ID",
    "ADMIN_HIDS",
    "PRIVACY_URL",
    "TERMS_URL",
    "CHANNEL_URL",
    "INSTITUTES",
    "INTAKE_CLOSED",
    "DATABASE_URL",
    "GROQ_API_KEY",
)


def full_environment() -> dict[str, str]:
    return {
        "BOT_TOKEN": FAKE_TOKEN,
        "ADMIN_CHAT_ID": "-1001234567890",
        "ADMIN_HIDS": "hid-one, hid-two;hid-three",
        "PRIVACY_URL": "https://example.com/privacy",
        "TERMS_URL": "https://example.com/terms",
        "CHANNEL_URL": "https://t.me/example",
        "INSTITUTES": "ИРИТ-РТФ, ИнЭУ\nГУК",
        "INTAKE_CLOSED": "true",
        "DATABASE_URL": FAKE_DATABASE_URL,
        "GROQ_API_KEY": FAKE_GROQ_KEY,
    }


def flush_handlers() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_config_parses_full_environment() -> None:
    config = Config.from_mapping(full_environment())

    assert config.bot_token == FAKE_TOKEN
    assert config.admin_chat_id == -1001234567890
    assert config.admin_hids == ("hid-one", "hid-two", "hid-three")
    assert config.privacy_url == "https://example.com/privacy"
    assert config.terms_url == "https://example.com/terms"
    assert config.channel_url == "https://t.me/example"
    assert config.institutes == ("ИРИТ-РТФ", "ИнЭУ", "ГУК")
    assert config.intake_closed is True
    assert config.database_url == FAKE_DATABASE_URL
    assert config.groq_api_key == FAKE_GROQ_KEY


def test_config_uses_safe_defaults_for_optional_values() -> None:
    config = Config.from_mapping({"BOT_TOKEN": FAKE_TOKEN})

    assert config.admin_chat_id is None
    assert config.admin_hids == ()
    assert config.privacy_url is None
    assert config.terms_url is None
    assert config.channel_url is None
    assert config.institutes == ()
    assert config.intake_closed is False
    assert config.database_url is None
    assert config.groq_api_key is None
    assert config.log_file.name == "logs.txt"


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"BOT_TOKEN": ""},
        {"BOT_TOKEN": "not-a-token"},
        {"BOT_TOKEN": "123456"},
    ],
)
def test_config_rejects_invalid_bot_token(values: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        Config.from_mapping(values)


@pytest.mark.parametrize(
    "values",
    [
        {"BOT_TOKEN": FAKE_TOKEN, "ADMIN_CHAT_ID": "chat"},
        {"BOT_TOKEN": FAKE_TOKEN, "INTAKE_CLOSED": "maybe"},
    ],
)
def test_config_rejects_invalid_values(values: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        Config.from_mapping(values)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
    ],
)
def test_config_parses_intake_closed(raw: str, expected: bool) -> None:
    config = Config.from_mapping(
        {"BOT_TOKEN": FAKE_TOKEN, "INTAKE_CLOSED": raw}
    )

    assert config.intake_closed is expected


def test_config_never_exposes_secrets_in_repr() -> None:
    config = Config.from_mapping(full_environment())

    representation = repr(config)

    for secret in config.secrets():
        assert secret not in representation
    assert FAKE_TOKEN not in representation
    assert FAKE_DATABASE_URL not in representation
    assert FAKE_GROQ_KEY not in representation


def test_config_secrets_skip_empty_optional_values() -> None:
    config = Config.from_mapping({"BOT_TOKEN": FAKE_TOKEN})

    assert config.secrets() == (FAKE_TOKEN,)


def test_load_config_from_explicit_mapping() -> None:
    config = load_config(environ={"BOT_TOKEN": FAKE_TOKEN})

    assert config.bot_token == FAKE_TOKEN


def test_load_config_reads_dotenv_file(monkeypatch, tmp_path: Path) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"BOT_TOKEN={FAKE_TOKEN}\nINTAKE_CLOSED=yes\n",
        encoding="utf-8",
    )

    config = load_config(env_file=env_file)

    assert config.bot_token == FAKE_TOKEN
    assert config.intake_closed is True


def test_setup_logging_creates_file_and_writes(tmp_path: Path) -> None:
    log_file = setup_logging(tmp_path / "logs.txt", console=False)

    logging.getLogger("test").info("hello from the test")
    flush_handlers()

    assert log_file == tmp_path / "logs.txt"
    assert "hello from the test" in log_file.read_text(encoding="utf-8")


def test_setup_logging_uses_home_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    log_file = setup_logging(console=False)

    assert log_file == tmp_path / "logs.txt"
    assert log_file.exists()


def test_default_rotation_matches_ten_megabyte_cap(tmp_path: Path) -> None:
    setup_logging(tmp_path / "logs.txt", console=False)

    handler = next(
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, RotatingFileHandler)
    )

    assert handler.backupCount == LOG_BACKUP_COUNT
    assert handler.maxBytes * (handler.backupCount + 1) == LOG_MAX_TOTAL_BYTES


def test_logging_keeps_total_size_within_cap(tmp_path: Path) -> None:
    setup_logging(
        tmp_path / "logs.txt",
        console=False,
        max_total_bytes=1200,
        backup_count=2,
    )

    logger = logging.getLogger("rotation")
    for _ in range(100):
        logger.info("x" * 100)
    flush_handlers()

    files = list(tmp_path.glob("logs.txt*"))
    assert len(files) <= 3
    assert sum(path.stat().st_size for path in files) <= 1200


def test_logging_redacts_configured_secrets(tmp_path: Path) -> None:
    secret = "super-secret-value"
    log_file = setup_logging(
        tmp_path / "logs.txt",
        secrets=(secret,),
        console=False,
    )

    logging.getLogger("test").warning("leaked %s", secret)
    flush_handlers()

    content = log_file.read_text(encoding="utf-8")
    assert secret not in content
    assert REDACTED in content


def test_redaction_filter_prefers_longer_secrets() -> None:
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "value=%s",
        ("abcdef",),
        None,
    )

    SecretRedactionFilter(("abc", "abcdef")).filter(record)

    assert record.getMessage() == f"value={REDACTED}"
