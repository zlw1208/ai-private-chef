from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class AdminThreadSummary(BaseModel):
    thread_id: str
    kind: Literal["recognition", "recipes", "other"]
    checkpoint_count: int
    last_updated_at: datetime


class AdminOverview(BaseModel):
    environment: str
    checkpointer_backend: Literal["sqlite", "postgres"]
    thread_count: int
    checkpoint_count: int
    truncated: bool
    threads: list[AdminThreadSummary]


class AdminThreadDetail(BaseModel):
    thread_id: str
    kind: Literal["recognition", "recipes", "other"]
    checkpoint_count: int
    last_updated_at: datetime
    latest_checkpoint_id: str
    latest_state: dict[str, Any]
