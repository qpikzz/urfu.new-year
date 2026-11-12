"""Single entry point of Urfu27bot."""

from __future__ import annotations

import asyncio
import logging
import sys

from app.bot import run_bot
from app.config import Config, ConfigError, load_config
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def _startup() -> Config | None:
    """Load configuration and configure logging."""
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return None

    setup_logging(config.log_file, secrets=config.secrets())
    logger.info("Configuration loaded: %s", config.public_summary())
    logger.info("Application started")
    return config


def main() -> int:
    """Prepare the application without starting polling."""
    return 0 if _startup() is not None else 1


async def amain() -> int:
    """Load the application and run the bot until it stops."""
    config = _startup()
    if config is None:
        return 1

    try:
        await run_bot(config)
    except ConfigError as exc:
        logger.error("Bot startup failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
