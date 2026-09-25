from datetime import datetime
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple

from backend.app.core.config import Settings
from backend.app.schemas.admin import (
    AdminOverview,
    AdminThreadDetail,
    AdminThreadSummary,
)

ThreadKind = Literal["recognition", "recipes", "other"]


def thread_kind(thread_id: str) -> ThreadKind:
    if thread_id.endswith(":recipes"):
        return "recipes"
    if thread_id:
        return "recognition"
    return "other"


def checkpoint_thread_id(item: CheckpointTuple) -> str:
    return str(item.config.get("configurable", {}).get("thread_id", ""))


def checkpoint_timestamp(item: CheckpointTuple) -> datetime:
    return datetime.fromisoformat(str(item.checkpoint["ts"]).replace("Z", "+00:00"))


def build_overview(
    settings: Settings,
    checkpointer: BaseCheckpointSaver[str],
    *,
    scan_limit: int = 1000,
) -> AdminOverview:
    items = list(checkpointer.list(None, limit=scan_limit))
    grouped: dict[str, list[CheckpointTuple]] = {}
    for item in items:
        thread_id = checkpoint_thread_id(item)
        if thread_id:
            grouped.setdefault(thread_id, []).append(item)

    threads = [
        AdminThreadSummary(
            thread_id=thread_id,
            kind=thread_kind(thread_id),
            checkpoint_count=len(checkpoints),
            last_updated_at=max(checkpoint_timestamp(item) for item in checkpoints),
        )
        for thread_id, checkpoints in grouped.items()
    ]
    threads.sort(key=lambda item: item.last_updated_at, reverse=True)
    return AdminOverview(
        environment=settings.app_env,
        checkpointer_backend=settings.checkpointer_backend,
        thread_count=len(threads),
        checkpoint_count=len(items),
        truncated=len(items) == scan_limit,
        threads=threads,
    )


def build_thread_detail(
    checkpointer: BaseCheckpointSaver[str],
    thread_id: str,
    *,
    scan_limit: int = 1000,
) -> AdminThreadDetail | None:
    config = {"configurable": {"thread_id": thread_id}}
    checkpoints = list(checkpointer.list(config, limit=scan_limit))
    if not checkpoints:
        return None
    latest = max(checkpoints, key=checkpoint_timestamp)
    raw_state = latest.checkpoint.get("channel_values", {})
    state: Any = jsonable_encoder(raw_state)
    if not isinstance(state, dict):
        state = {"value": state}
    return AdminThreadDetail(
        thread_id=thread_id,
        kind=thread_kind(thread_id),
        checkpoint_count=len(checkpoints),
        last_updated_at=checkpoint_timestamp(latest),
        latest_checkpoint_id=str(latest.checkpoint["id"]),
        latest_state=state,
    )
