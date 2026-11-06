"""Single entry point of Urfu27bot."""

from __future__ import annotations

import logging
import sys

from app.config import ConfigError, load_config
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> int:
    """Load configuration, configure logging and start the application."""
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    setup_logging(config.log_file, secrets=config.secrets())
    logger.info("Configuration loaded: %s", config.public_summary())
    logger.info("Application started; no handlers are registered yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
