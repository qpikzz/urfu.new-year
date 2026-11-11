"""Small adapter over the author-supplied HID encoding module (DATA 1)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

_SECURITY_DIR = Path(__file__).resolve().parent.parent / "security"
_AUTHOR_MODULE_NAME = "HID"

_author_module_cache: ModuleType | None = None


class HIDError(ValueError):
    """Raised when HID conversion is unavailable or its input is invalid."""


def _load_author_module() -> ModuleType:
    if str(_SECURITY_DIR) not in sys.path:
        sys.path.insert(0, str(_SECURITY_DIR))
    try:
        return __import__(_AUTHOR_MODULE_NAME)
    except ImportError as exc:
        raise HIDError("HID module is not available") from exc


def _author_module() -> ModuleType:
    global _author_module_cache
    if _author_module_cache is None:
        _author_module_cache = _load_author_module()
    return _author_module_cache


def _ensure_keys(module: ModuleType) -> None:
    keys = getattr(module, "CRYPT_KEY", ())
    try:
        configured = len(keys) >= 2 and bool(keys[0]) and bool(keys[1])
    except TypeError as exc:
        raise HIDError("HID encoding keys are not configured") from exc
    if not configured:
        raise HIDError("HID encoding keys are not configured")


def telegram_id_to_hid(telegram_id: int) -> str:
    """Encode a Telegram user ID with the author's module."""
    if isinstance(telegram_id, bool) or not isinstance(telegram_id, int):
        raise HIDError("Telegram ID must be an integer")
    if telegram_id <= 0:
        raise HIDError("Telegram ID must be positive")

    module = _author_module()
    _ensure_keys(module)
    try:
        hid = module.encrypt(telegram_id)
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise HIDError("Failed to encode the Telegram ID") from exc
    if not isinstance(hid, str) or not hid:
        raise HIDError("HID module returned an invalid identifier")
    return hid


def hid_to_telegram_id(hid: str) -> int:
    """Decode an HID with the author's module."""
    if not isinstance(hid, str) or not hid.strip():
        raise HIDError("HID must be a non-empty string")

    module = _author_module()
    _ensure_keys(module)
    try:
        value = module.decrypt(hid)
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise HIDError("Failed to decode the HID") from exc

    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise HIDError("HID module returned an invalid Telegram ID")
