import sqlite3
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver

from backend.app.core.config import Settings


class CheckpointerConfigurationError(RuntimeError):
    """Raised when the configured checkpoint backend cannot be initialized."""


def create_sqlite_checkpointer(path: Path) -> SqliteSaver:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return checkpointer


def normalize_postgres_dsn(database_url: str) -> str:
    """Convert SQLAlchemy-style psycopg URLs into psycopg connection strings."""
    if database_url.startswith("postgresql+psycopg://"):
        return "postgresql://" + database_url.removeprefix("postgresql+psycopg://")
    if database_url.startswith(("postgresql://", "postgres://")):
        return database_url
    raise CheckpointerConfigurationError(
        "DATABASE_URL must use postgresql:// or postgresql+psycopg:// "
        "when CHECKPOINTER_BACKEND=postgres"
    )


class CheckpointManager:
    """Own the process-wide checkpointer and its database connection lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._checkpointer: BaseCheckpointSaver[str] | None = None
        self._context: AbstractContextManager[Any] | None = None

    def open(self) -> BaseCheckpointSaver[str]:
        if self._checkpointer is not None:
            return self._checkpointer

        if self._settings.checkpointer_backend == "sqlite":
            self._checkpointer = create_sqlite_checkpointer(
                self._settings.checkpoint_sqlite_path
            )
            return self._checkpointer

        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise CheckpointerConfigurationError(
                "PostgreSQL checkpoint support is not installed; "
                "install the project with the 'postgres' extra"
            ) from exc

        dsn = normalize_postgres_dsn(self._settings.database_url)
        self._context = PostgresSaver.from_conn_string(dsn)
        try:
            checkpointer = self._context.__enter__()
            checkpointer.setup()
        except Exception:
            self._context.__exit__(*sys.exc_info())
            self._context = None
            raise
        self._checkpointer = checkpointer
        return checkpointer

    def close(self) -> None:
        checkpointer = self._checkpointer
        context = self._context
        self._checkpointer = None
        self._context = None

        if context is not None:
            context.__exit__(None, None, None)
        elif isinstance(checkpointer, SqliteSaver):
            checkpointer.conn.close()
