from collections.abc import Iterator

from fastapi.testclient import TestClient
from langgraph.checkpoint.base import CheckpointTuple

from backend.app.api.dependencies import get_checkpointer
from backend.app.core.config import Settings, get_settings
from backend.app.main import app


class FakeCheckpointer:
    def __init__(self) -> None:
        self.items = [
            CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": "thread-1:recipes",
                        "checkpoint_id": "checkpoint-2",
                    }
                },
                checkpoint={
                    "id": "checkpoint-2",
                    "ts": "2026-09-24T09:30:00+00:00",
                    "channel_values": {"user_message": "番茄炒蛋", "recipes": ["番茄炒蛋"]},
                },
                metadata={"source": "loop", "step": 1, "parents": {}},
            ),
            CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": "thread-1:recipes",
                        "checkpoint_id": "checkpoint-1",
                    }
                },
                checkpoint={
                    "id": "checkpoint-1",
                    "ts": "2026-09-24T09:29:00+00:00",
                    "channel_values": {"user_message": "番茄炒蛋"},
                },
                metadata={"source": "input", "step": -1, "parents": {}},
            ),
            CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": "thread-2",
                        "checkpoint_id": "checkpoint-3",
                    }
                },
                checkpoint={
                    "id": "checkpoint-3",
                    "ts": "2026-09-24T09:31:00+00:00",
                    "channel_values": {"object_key": "uploads/example.jpg"},
                },
                metadata={"source": "loop", "step": 1, "parents": {}},
            ),
        ]

    def list(self, config=None, *, filter=None, before=None, limit=None) -> Iterator:
        del filter, before
        items = self.items
        if config is not None:
            thread_id = config["configurable"]["thread_id"]
            items = [
                item
                for item in items
                if item.config["configurable"]["thread_id"] == thread_id
            ]
        yield from items[:limit]


def test_admin_page_rejects_non_local_host() -> None:
    with TestClient(app, base_url="http://example.com") as client:
        response = client.get("/admin")

    assert response.status_code == 403


def test_admin_overview_and_thread_detail_are_available_locally() -> None:
    app.dependency_overrides[get_checkpointer] = lambda: FakeCheckpointer()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        app_env="test",
        checkpointer_backend="postgres",
    )
    try:
        with TestClient(app, base_url="http://127.0.0.1") as client:
            page = client.get("/admin")
            overview = client.get("/api/admin/overview")
            detail = client.get("/api/admin/threads/thread-1:recipes")
    finally:
        app.dependency_overrides.clear()

    assert page.status_code == 200
    assert "本机后台" in page.text
    assert overview.status_code == 200
    assert overview.json()["thread_count"] == 2
    assert overview.json()["checkpoint_count"] == 3
    assert overview.json()["checkpointer_backend"] == "postgres"
    assert detail.status_code == 200
    assert detail.json()["checkpoint_count"] == 2
    assert detail.json()["latest_state"]["recipes"] == ["番茄炒蛋"]
