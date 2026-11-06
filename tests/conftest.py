from __future__ import annotations

import pytest

from app.logging_setup import reset_logging


@pytest.fixture(autouse=True)
def reset_application_logging() -> None:
    yield
    reset_logging()
