from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

COMMAND_HANDLERS = {
    "start",
    "menu",
    "new",
    "look",
    "ban",
    "accept",
    "reject",
    "about",
    "stats",
    "send",
    "close",
}


def test_run_entry_point_returns_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:fake")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    from run import main

    assert main() == 0

    log_file = tmp_path / "logs.txt"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Application started" in content
    assert "123456:fake" not in content


def test_handler_files_match_commands() -> None:
    handlers_dir = ROOT / "app" / "handlers"
    files = {path.stem for path in handlers_dir.glob("*.py")} - {"__init__"}

    assert files == COMMAND_HANDLERS


@pytest.mark.parametrize("command", sorted(COMMAND_HANDLERS))
def test_handler_module_exposes_router(command: str) -> None:
    module = importlib.import_module(f"app.handlers.{command}")

    assert module.router is not None


def test_keyboards_and_content_modules_are_importable() -> None:
    import app.content
    import app.keyboards

    assert app.content is not None
    assert app.keyboards is not None


def test_env_example_contains_only_empty_values() -> None:
    content = (ROOT / ".env.example").read_text(encoding="utf-8")

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        name, separator, value = stripped.partition("=")
        assert separator == "=", f"Malformed line: {line}"
        assert name, f"Missing name: {line}"
        assert value == "", f"Value must be empty: {line}"


def test_gitignore_covers_runtime_artifacts() -> None:
    lines = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    }

    for pattern in (
        ".env",
        "/logs.txt",
        "/tmp/",
        "/models/",
        "/forbidden_words/",
        "/backups/",
        "/triples*.csv",
    ):
        assert pattern in lines
