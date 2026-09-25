import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_settings_default_to_sqlite() -> None:
    settings = Settings(_env_file=None)

    assert settings.checkpointer_backend == "sqlite"
    assert settings.database_url.startswith("sqlite+aiosqlite:///")


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_log_level="verbose")


def test_blank_dashscope_model_uses_default() -> None:
    settings = Settings(_env_file=None, dashscope_model="")

    assert settings.dashscope_model == "qwen3.7-plus"
