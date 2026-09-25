from uuid import UUID

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_recognition_agent
from backend.app.main import app
from backend.app.schemas.recognition import Ingredient, IngredientRecognition

OBJECT_KEY = "uploads/2026/09/23/12345678-1234-1234-1234-123456789abc.jpg"
THREAD_ID = "12345678-1234-1234-1234-123456789abc"


class StubRecognitionAgent:
    def recognize(self, *, object_key: str, thread_id: UUID, user_text: str):
        assert object_key == OBJECT_KEY
        assert str(thread_id) == THREAD_ID
        assert user_text == "请重点看左下角"
        return IngredientRecognition(
            is_food_image=True,
            summary="识别到一个土豆。",
            ingredients=[
                Ingredient(
                    name_zh="土豆",
                    quantity_estimate="约1个",
                    visible_state="完整",
                    confidence=0.91,
                )
            ],
            possible_non_food_items=[],
            uncertainty_note="",
        )


def test_recognize_ingredients_endpoint() -> None:
    app.dependency_overrides[get_recognition_agent] = StubRecognitionAgent
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/recognitions",
                json={
                    "object_key": OBJECT_KEY,
                    "thread_id": THREAD_ID,
                    "user_text": "请重点看左下角",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["thread_id"] == THREAD_ID
    assert payload["recognition"]["ingredients"][0]["name_zh"] == "土豆"

