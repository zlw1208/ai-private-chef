from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from backend.app.agent.recognition import (
    RecognitionAgent,
    RecognitionConfigurationError,
)
from backend.app.core.checkpoints import create_sqlite_checkpointer
from backend.app.core.config import Settings
from backend.app.schemas.recognition import Ingredient, IngredientRecognition
from backend.app.services.oss_service import PresignedDownload, VerifiedUpload

OBJECT_KEY = "uploads/2026/09/23/12345678-1234-1234-1234-123456789abc.jpg"


class FakeOSSService:
    def __init__(self) -> None:
        self.verified_keys: list[str] = []

    def verify_uploaded_image(self, object_key: str) -> VerifiedUpload:
        self.verified_keys.append(object_key)
        return VerifiedUpload(object_key, "image/jpeg", 1024)

    def create_model_download_url(self, object_key: str) -> PresignedDownload:
        return PresignedDownload(
            object_key=object_key,
            download_url="https://example.invalid/signed-image.jpg",
            expires_at=datetime(2026, 9, 23, 12, 5, tzinfo=UTC),
        )


class FakeStructuredModel:
    def __init__(self) -> None:
        self.messages = None

    def invoke(self, messages, config=None):
        self.messages = messages
        return IngredientRecognition(
            is_food_image=True,
            summary="图片中有西红柿和鸡蛋。",
            ingredients=[
                Ingredient(
                    name_zh="西红柿",
                    quantity_estimate="约2个",
                    visible_state="新鲜",
                    confidence=0.96,
                ),
                Ingredient(
                    name_zh="鸡蛋",
                    quantity_estimate="约3个",
                    visible_state="完整",
                    confidence=0.94,
                ),
            ],
            possible_non_food_items=[],
            uncertainty_note="",
        )


class FakeModel:
    def __init__(self) -> None:
        self.structured = FakeStructuredModel()
        self.schema = None

    def with_structured_output(self, schema, **_):
        self.schema = schema
        return self.structured


def make_settings(checkpoint_path: Path | None = None) -> Settings:
    return Settings(
        _env_file=None,
        dashscope_api_key=SecretStr("test-key"),
        dashscope_model="qwen3.7-plus",
        oss_bucket="test-bucket",
        checkpoint_sqlite_path=checkpoint_path or Path("ignored.sqlite"),
    )


def test_recognition_graph_uses_signed_url_and_returns_structured_result() -> None:
    oss_service = FakeOSSService()
    model = FakeModel()
    agent = RecognitionAgent(
        make_settings(),
        oss_service,
        InMemorySaver(),
        model=model,
    )
    thread_id = uuid4()

    result = agent.recognize(
        object_key=OBJECT_KEY,
        thread_id=thread_id,
        user_text="这是我冰箱里的食材",
    )

    assert result.ingredients[0].name_zh == "西红柿"
    assert oss_service.verified_keys == [OBJECT_KEY]
    assert model.schema is IngredientRecognition
    human_message = model.structured.messages[1]
    assert human_message.content[1]["image_url"]["url"].startswith("https://")

    snapshot = agent.graph.get_state({"configurable": {"thread_id": str(thread_id)}})
    assert snapshot.values["object_key"] == OBJECT_KEY
    assert snapshot.values["recognition"]["summary"] == "图片中有西红柿和鸡蛋。"
    assert "image_url" not in snapshot.values


def test_sqlite_checkpointer_persists_graph_state(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoints.sqlite"
    checkpointer = create_sqlite_checkpointer(checkpoint_path)
    agent = RecognitionAgent(
        make_settings(checkpoint_path),
        FakeOSSService(),
        checkpointer,
        model=FakeModel(),
    )
    thread_id = uuid4()

    agent.recognize(object_key=OBJECT_KEY, thread_id=thread_id)

    assert checkpoint_path.exists()
    tuple_result = checkpointer.get_tuple(
        {"configurable": {"thread_id": str(thread_id)}}
    )
    assert tuple_result is not None
    checkpointer.conn.close()


def test_recognition_agent_requires_dashscope_key() -> None:
    settings = make_settings()
    settings.dashscope_api_key = None

    with pytest.raises(RecognitionConfigurationError, match="DASHSCOPE_API_KEY"):
        RecognitionAgent(settings, FakeOSSService(), InMemorySaver())
