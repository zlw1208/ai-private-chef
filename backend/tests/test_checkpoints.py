import sys
from contextlib import contextmanager
from types import ModuleType

import pytest

from backend.app.core.checkpoints import (
    CheckpointerConfigurationError,
    CheckpointManager,
    normalize_postgres_dsn,
)
from backend.app.core.config import Settings


def test_normalize_postgres_dsn_accepts_psycopg_sqlalchemy_url() -> None:
    assert (
        normalize_postgres_dsn("postgresql+psycopg://chef:secret@db:5432/chef")
        == "postgresql://chef:secret@db:5432/chef"
    )


def test_normalize_postgres_dsn_rejects_non_postgres_url() -> None:
    with pytest.raises(CheckpointerConfigurationError, match="DATABASE_URL"):
        normalize_postgres_dsn("sqlite:///local.db")


def test_postgres_manager_sets_up_and_closes_checkpointer(monkeypatch) -> None:
    events: list[object] = []

    class FakeCheckpointer:
        def setup(self) -> None:
            events.append("setup")

    fake_checkpointer = FakeCheckpointer()

    class FakePostgresSaver:
        @classmethod
        @contextmanager
        def from_conn_string(cls, dsn: str):
            events.append(dsn)
            try:
                yield fake_checkpointer
            finally:
                events.append("closed")

    package = ModuleType("langgraph.checkpoint.postgres")
    package.PostgresSaver = FakePostgresSaver
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres", package)

    settings = Settings(
        _env_file=None,
        checkpointer_backend="postgres",
        database_url="postgresql+psycopg://chef:secret@db:5432/chef",
    )
    manager = CheckpointManager(settings)

    assert manager.open() is fake_checkpointer
    assert manager.open() is fake_checkpointer
    manager.close()

    assert events == [
        "postgresql://chef:secret@db:5432/chef",
        "setup",
        "closed",
    ]
