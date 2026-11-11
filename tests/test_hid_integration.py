from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app import hid

FAKE_KEYS = ("0123456789", "abcdefghij")


def fake_module(*, encrypt=None, decrypt=None, keys=FAKE_KEYS):
    return SimpleNamespace(
        CRYPT_KEY=keys,
        encrypt=encrypt or (lambda telegram_id: f"hid-{telegram_id}"),
        decrypt=decrypt or (lambda value: value.removeprefix("hid-")),
    )


@pytest.fixture
def author_module(monkeypatch):
    try:
        module = hid._author_module()
    except hid.HIDError:
        pytest.skip("author HID module is not available")
    monkeypatch.setattr(module, "CRYPT_KEY", FAKE_KEYS)
    return module


def test_author_module_is_loaded_from_security_directory(author_module) -> None:
    assert Path(author_module.__file__).resolve().parent.name == "security"


def test_round_trip_with_author_module(author_module) -> None:
    value = hid.telegram_id_to_hid(123456789)

    assert isinstance(value, str)
    assert value
    assert value != "123456789"
    assert hid.hid_to_telegram_id(value) == 123456789


@pytest.mark.parametrize("telegram_id", [0, -1, True, "123", 1.5, None])
def test_encode_rejects_invalid_telegram_id(monkeypatch, telegram_id) -> None:
    monkeypatch.setattr(hid, "_author_module_cache", fake_module())

    with pytest.raises(hid.HIDError):
        hid.telegram_id_to_hid(telegram_id)


@pytest.mark.parametrize("value", ["", "   ", 123, None, b"hid"])
def test_decode_rejects_invalid_hid(monkeypatch, value) -> None:
    monkeypatch.setattr(hid, "_author_module_cache", fake_module())

    with pytest.raises(hid.HIDError):
        hid.hid_to_telegram_id(value)


def test_encode_requires_configured_keys(monkeypatch) -> None:
    def fail(_telegram_id: int) -> str:
        pytest.fail("the author algorithm must not be called without keys")

    monkeypatch.setattr(
        hid, "_author_module_cache", fake_module(encrypt=fail, keys=())
    )

    with pytest.raises(hid.HIDError, match="keys"):
        hid.telegram_id_to_hid(1)


def test_decode_requires_configured_keys(monkeypatch) -> None:
    def fail(_value: str) -> str:
        pytest.fail("the author algorithm must not be called without keys")

    monkeypatch.setattr(
        hid, "_author_module_cache", fake_module(decrypt=fail, keys=())
    )

    with pytest.raises(hid.HIDError, match="keys"):
        hid.hid_to_telegram_id("hid")


def test_encode_wraps_algorithm_errors(monkeypatch) -> None:
    def fail(_telegram_id: int) -> str:
        raise ValueError("bad alphabet")

    monkeypatch.setattr(hid, "_author_module_cache", fake_module(encrypt=fail))

    with pytest.raises(hid.HIDError) as error:
        hid.telegram_id_to_hid(1)

    assert isinstance(error.value.__cause__, ValueError)


def test_decode_wraps_algorithm_errors(monkeypatch) -> None:
    def fail(_value: str) -> str:
        raise IndexError("bad alphabet")

    monkeypatch.setattr(hid, "_author_module_cache", fake_module(decrypt=fail))

    with pytest.raises(hid.HIDError) as error:
        hid.hid_to_telegram_id("hid")

    assert isinstance(error.value.__cause__, IndexError)


def test_encode_rejects_non_string_result(monkeypatch) -> None:
    monkeypatch.setattr(
        hid, "_author_module_cache", fake_module(encrypt=lambda _telegram_id: 123)
    )

    with pytest.raises(hid.HIDError):
        hid.telegram_id_to_hid(1)


@pytest.mark.parametrize("result", ["123456789", 123456789])
def test_decode_accepts_string_and_integer_results(monkeypatch, result) -> None:
    monkeypatch.setattr(
        hid, "_author_module_cache", fake_module(decrypt=lambda _value: result)
    )

    assert hid.hid_to_telegram_id("hid") == 123456789


@pytest.mark.parametrize("result", ["not-a-number", "", True, None, 1.5])
def test_decode_rejects_invalid_algorithm_result(monkeypatch, result) -> None:
    monkeypatch.setattr(
        hid, "_author_module_cache", fake_module(decrypt=lambda _value: result)
    )

    with pytest.raises(hid.HIDError):
        hid.hid_to_telegram_id("hid")


def test_missing_author_module_is_reported_as_hid_error(monkeypatch) -> None:
    def fail() -> None:
        raise hid.HIDError("HID module is not available")

    monkeypatch.setattr(hid, "_author_module_cache", None)
    monkeypatch.setattr(hid, "_load_author_module", fail)

    with pytest.raises(hid.HIDError, match="not available"):
        hid.telegram_id_to_hid(1)
