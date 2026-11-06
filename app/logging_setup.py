"""Application logging with rotation and secret redaction."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_MAX_TOTAL_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 9
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
REDACTED = "[REDACTED]"

_HANDLER_MARKER = "_urfu27bot_handler"


class SecretRedactionFilter(logging.Filter):
    """Replace configured secrets in log messages before they are written."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = tuple(
            sorted({secret for secret in secrets if secret}, key=len, reverse=True)
        )

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True

        message = record.getMessage()
        for secret in self._secrets:
            message = message.replace(secret, REDACTED)
        record.msg = message
        record.args = None
        return True


def _make_formatter() -> logging.Formatter:
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    formatter.converter = time.gmtime
    return formatter


def _mark(handler: logging.Handler) -> None:
    setattr(handler, _HANDLER_MARKER, True)


def _is_marked(handler: logging.Handler) -> bool:
    return bool(getattr(handler, _HANDLER_MARKER, False))


def reset_logging() -> None:
    """Remove handlers installed by :func:`setup_logging`."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if _is_marked(handler):
            root.removeHandler(handler)
            handler.close()


def setup_logging(
    log_file: str | Path | None = None,
    *,
    level: int = logging.INFO,
    secrets: Iterable[str] = (),
    console: bool = True,
    max_total_bytes: int = LOG_MAX_TOTAL_BYTES,
    backup_count: int = LOG_BACKUP_COUNT,
) -> Path:
    """Configure the root logger and return the resolved log file path.

    The file and all rotated copies together never exceed ``max_total_bytes``.
    Only HIDs, circle IDs and recognized text may be written to the log; the
    redaction filter additionally masks configured secrets.
    """
    path = Path(log_file) if log_file is not None else Path.home() / "logs.txt"
    if backup_count < 1:
        raise ValueError("backup_count must be at least 1")
    if max_total_bytes <= backup_count:
        raise ValueError("max_total_bytes is too small")

    max_bytes = max_total_bytes // (backup_count + 1)
    path.parent.mkdir(parents=True, exist_ok=True)

    reset_logging()

    root = logging.getLogger()
    root.setLevel(level)
    formatter = _make_formatter()
    redaction = SecretRedactionFilter(secrets)

    file_handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redaction)
    _mark(file_handler)
    root.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(redaction)
        _mark(console_handler)
        root.addHandler(console_handler)

    return path
