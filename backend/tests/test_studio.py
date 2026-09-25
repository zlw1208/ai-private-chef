import base64

import pytest
from langchain_core.messages import HumanMessage

from backend.app import studio
from backend.app.schemas.recognition import Ingredient, IngredientRecognition
from backend.app.services.oss_service import InvalidUploadError, VerifiedUpload


class FakeStudioOSSService:
    def __init__(self) -> None:
        self.uploaded: tuple[bytes, str] | None = None

    def upload_image_bytes(self, *, data: bytes, content_type: str) -> VerifiedUpload:
        self.uploaded = (data, content_type)
        return VerifiedUpload(
            object_key="uploads/2026/09/25/12345678-1234-1234-1234-123456789abc.png",
            content_type=content_type,
            size_bytes=len(data),
        )


class FakeStudioRecognitionAgent:
    def recognize(self, **_: object) -> IngredientRecognition:
        return IngredientRecognition(
            is_food_image=True,
            summary="图片中有鸡蛋和番茄。",
            ingredients=[
                Ingredient(
                    name_zh="鸡蛋",
                    quantity_estimate="3个",
                    visible_state="完整",
                    confidence=0.98,
                )
            ],
            possible_non_food_items=[],
            uncertainty_note="",
        )


def image_block(data: bytes = b"\x89PNG\r\n\x1a\nimage") -> dict[str, object]:
    return {
        "type": "image",
        "data": base64.b64encode(data).decode("ascii"),
        "source_type": "base64",
        "mime_type": "image/png",
        "metadata": {"filename": "ingredients.png"},
    }


def test_prepare_request_uploads_studio_image_to_oss(monkeypatch) -> None:
    fake_oss = FakeStudioOSSService()
    monkeypatch.setattr(studio, "_get_oss_service", lambda: fake_oss)

    result = studio.prepare_request(
        {
            "messages": [
                HumanMessage(
                    content=[
                        {"type": "text", "text": "这些食材能做什么菜"},
                        image_block(),
                    ]
                )
            ]
        }
    )

    assert result["user_message"] == "这些食材能做什么菜"
    assert result["image_object_key"].endswith(".png")
    assert fake_oss.uploaded is not None
    assert fake_oss.uploaded[1] == "image/png"
    assert studio.route_after_prepare(result) == "recognize"


def test_recognize_image_maps_result_into_recipe_state(monkeypatch) -> None:
    monkeypatch.setattr(
        studio,
        "_get_recognition_agent",
        lambda: FakeStudioRecognitionAgent(),
    )

    result = studio.recognize_image(
        {
            "user_message": "这些食材能做什么菜",
            "image_object_key": (
                "uploads/2026/09/25/12345678-1234-1234-1234-123456789abc.png"
            ),
        },
        {"configurable": {"thread_id": "01a0d74a-4880-7ea2-b7c0-620f8ea5b0e0"}},
    )

    assert result["ingredients"] == [
        {"name": "鸡蛋", "quantity": "3个", "state": "完整"}
    ]
    assert result["image_context"] == {
        "is_food_image": True,
        "summary": "图片中有鸡蛋和番茄。",
    }


def test_decode_studio_image_rejects_invalid_base64() -> None:
    with pytest.raises(InvalidUploadError, match="valid base64"):
        studio._decode_studio_image(
            {
                "type": "image",
                "source_type": "base64",
                "mime_type": "image/png",
                "data": "not base64!",
            },
            max_size_bytes=1024,
        )
