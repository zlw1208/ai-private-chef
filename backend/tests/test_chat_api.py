import json
from uuid import UUID

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_recipe_agent, get_recognition_agent
from backend.app.main import app
from backend.app.schemas.recognition import Ingredient, IngredientRecognition

OBJECT_KEY = "uploads/2026/09/24/12345678-1234-1234-1234-123456789abc.jpg"
THREAD_ID = "12345678-1234-1234-1234-123456789abc"


class StubRecognitionAgent:
    def recognize(self, *, object_key: str, thread_id: UUID, user_text: str):
        assert object_key == OBJECT_KEY
        assert str(thread_id) == THREAD_ID
        assert user_text == "想吃清淡一点"
        return IngredientRecognition(
            is_food_image=True,
            summary="图片中有鸡蛋和番茄。",
            ingredients=[
                Ingredient(
                    name_zh="鸡蛋",
                    quantity_estimate="2个",
                    visible_state="完整",
                    confidence=0.98,
                ),
                Ingredient(
                    name_zh="番茄",
                    quantity_estimate="2个",
                    visible_state="新鲜",
                    confidence=0.96,
                ),
            ],
            possible_non_food_items=[],
            uncertainty_note="",
        )


class StubRecipeAgent:
    def stream_recommendation(
        self,
        *,
        message: str,
        ingredients: list,
        image_context,
        thread_id: UUID,
    ):
        assert message == "想吃清淡一点"
        assert [item.name for item in ingredients] == ["鸡蛋", "番茄"]
        assert image_context.is_food_image is True
        assert image_context.summary == "图片中有鸡蛋和番茄。"
        assert str(thread_id) == THREAD_ID
        yield {"type": "meta", "tool_used": "none", "tool_reason": "家常菜无需联网"}
        yield {"type": "status", "message": "正在为你设计菜谱…"}
        yield {"type": "delta", "content": "可以做一道"}
        yield {"type": "delta", "content": "少油番茄炒蛋。"}


def test_chat_stream_emits_workflow_and_content_events() -> None:
    app.dependency_overrides[get_recognition_agent] = lambda: StubRecognitionAgent()
    app.dependency_overrides[get_recipe_agent] = lambda: StubRecipeAgent()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/chat/stream",
                json={
                    "message": "想吃清淡一点",
                    "object_key": OBJECT_KEY,
                    "thread_id": THREAD_ID,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [event["type"] for event in events[:4]] == [
        "status",
        "recognition",
        "meta",
        "status",
    ]
    assert any(event.get("tool_used") == "none" for event in events)
    assert "少油番茄炒蛋" in "".join(
        event.get("content", "") for event in events if event["type"] == "delta"
    )
    assert events[-1]["type"] == "done"


def test_chat_stream_rejects_empty_request() -> None:
    app.dependency_overrides[get_recognition_agent] = lambda: StubRecognitionAgent()
    app.dependency_overrides[get_recipe_agent] = lambda: StubRecipeAgent()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/chat/stream",
                json={"message": "", "thread_id": THREAD_ID},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
