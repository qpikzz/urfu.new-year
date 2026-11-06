"""Loading and validation of the environment configuration."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_BOT_TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]+$")
_LIST_SEPARATOR = re.compile(r"[,;\s]+")
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class ConfigError(ValueError):
    """Raised when an environment variable is missing or invalid."""


def default_log_path() -> Path:
    """Return the log file path required by the infrastructure spec."""
    return Path.home() / "logs.txt"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _required(values: Mapping[str, str], name: str) -> str:
    value = _clean(values.get(name))
    if value is None:
        raise ConfigError(f"{name} is required")
    return value


def _optional(values: Mapping[str, str], name: str) -> str | None:
    return _clean(values.get(name))


def _parse_bool(values: Mapping[str, str], name: str) -> bool:
    value = _clean(values.get(name))
    if value is None:
        return False
    normalized = value.lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name} must be a boolean")


def _parse_list(values: Mapping[str, str], name: str) -> tuple[str, ...]:
    value = _clean(values.get(name))
    if value is None:
        return ()
    return tuple(item for item in _LIST_SEPARATOR.split(value) if item)


def _parse_bot_token(values: Mapping[str, str]) -> str:
    token = _required(values, "BOT_TOKEN")
    if _BOT_TOKEN_PATTERN.fullmatch(token) is None:
        raise ConfigError("BOT_TOKEN has an invalid format")
    return token


def _parse_admin_chat_id(values: Mapping[str, str]) -> int | None:
    value = _optional(values, "ADMIN_CHAT_ID")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError("ADMIN_CHAT_ID must be an integer") from exc


@dataclass(frozen=True, slots=True)
class Config:
    """Validated runtime configuration.

    Secret and environment-specific values are excluded from ``repr`` so the
    configuration can never leak them accidentally through logs.
    """

    bot_token: str = field(repr=False)
    admin_chat_id: int | None = field(default=None, repr=False)
    admin_hids: tuple[str, ...] = field(default=(), repr=False)
    privacy_url: str | None = field(default=None, repr=False)
    terms_url: str | None = field(default=None, repr=False)
    channel_url: str | None = field(default=None, repr=False)
    institutes: tuple[str, ...] = ()
    intake_closed: bool = False
    database_url: str | None = field(default=None, repr=False)
    groq_api_key: str | None = field(default=None, repr=False)
    log_file: Path = field(default_factory=default_log_path, repr=False)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Config:
        """Build a configuration from environment-like values."""
        return cls(
            bot_token=_parse_bot_token(values),
            admin_chat_id=_parse_admin_chat_id(values),
            admin_hids=_parse_list(values, "ADMIN_HIDS"),
            privacy_url=_optional(values, "PRIVACY_URL"),
            terms_url=_optional(values, "TERMS_URL"),
            channel_url=_optional(values, "CHANNEL_URL"),
            institutes=_parse_list(values, "INSTITUTES"),
            intake_closed=_parse_bool(values, "INTAKE_CLOSED"),
            database_url=_optional(values, "DATABASE_URL"),
            groq_api_key=_optional(values, "GROQ_API_KEY"),
        )

    def secrets(self) -> tuple[str, ...]:
        """Return values that must never appear in logs."""
        values = (
            self.bot_token,
            self.database_url,
            self.groq_api_key,
            self.privacy_url,
            self.terms_url,
            self.channel_url,
            None if self.admin_chat_id is None else str(self.admin_chat_id),
        )
        return tuple(value for value in values if value)

    def public_summary(self) -> dict[str, bool | int]:
        """Return safe diagnostic values for the startup log."""
        return {
            "admin_chat_configured": self.admin_chat_id is not None,
            "admin_hids": len(self.admin_hids),
            "institutes": len(self.institutes),
            "intake_closed": self.intake_closed,
        }


def load_config(
    env_file: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Config:
    """Load the configuration from a dotenv file and the process environment.

    An explicit ``environ`` mapping bypasses dotenv loading and is intended for
    tests and for callers that already have a filtered environment.
    """
    if environ is not None:
        return Config.from_mapping(environ)

    load_dotenv(dotenv_path=env_file, override=False)
    return Config.from_mapping(os.environ)
