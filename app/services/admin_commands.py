"""Argument parsing for administrator commands (FLOWS 11)."""

from __future__ import annotations


def command_argument(text: str | None) -> str | None:
    """Return everything after the command token, or None when it is absent."""
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    argument = parts[1].strip()
    return argument or None


def parse_cir_id(text: str | None) -> int | None:
    """Parse a positive circle identifier from a command message."""
    argument = command_argument(text)
    if argument is None or not argument.isdigit():
        return None
    cir_id = int(argument)
    return cir_id if cir_id > 0 else None


__all__ = ["command_argument", "parse_cir_id"]
