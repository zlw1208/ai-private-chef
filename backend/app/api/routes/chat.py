import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.api.dependencies import (
    RecipeAgentDependency,
    RecognitionAgentDependency,
)
from backend.app.core.logging import get_logger
from backend.app.schemas.chat import ChatStreamRequest
from backend.app.schemas.recipes import RecipeImageContext, RecipeIngredientInput
from backend.app.schemas.recognition import IngredientRecognition

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


def _event(event_type: str, **data: Any) -> bytes:
    return (
        json.dumps({"type": event_type, **data}, ensure_ascii=False) + "\n"
    ).encode("utf-8")


@router.post("/stream")
def stream_chat(
    payload: ChatStreamRequest,
    recognition_agent: RecognitionAgentDependency,
    recipe_agent: RecipeAgentDependency,
) -> StreamingResponse:
    def generate() -> Iterator[bytes]:
        try:
            recognition: IngredientRecognition | None = None
            ingredients: list[RecipeIngredientInput] = []
            image_context: RecipeImageContext | None = None

            if payload.object_key:
                yield _event("status", message="正在识别图片中的食材…")
                recognition = recognition_agent.recognize(
                    object_key=payload.object_key,
                    thread_id=payload.thread_id,
                    user_text=payload.message,
                )
                ingredients = [
                    RecipeIngredientInput(
                        name=item.name_zh,
                        quantity=item.quantity_estimate,
                        state=item.visible_state,
                    )
                    for item in recognition.ingredients
                ]
                image_context = RecipeImageContext(
                    is_food_image=recognition.is_food_image,
                    summary=recognition.summary,
                )
                yield _event(
                    "recognition",
                    summary=recognition.summary,
                    is_food_image=recognition.is_food_image,
                    ingredients=[item.model_dump() for item in recognition.ingredients],
                )

            message = payload.message.strip()
            if not message:
                message = "请根据刚才上传的图片推荐合适的菜谱。"

            for agent_event in recipe_agent.stream_recommendation(
                message=message,
                ingredients=ingredients,
                image_context=image_context,
                thread_id=payload.thread_id,
            ):
                event_type = str(agent_event.get("type", "status"))
                event_data = {
                    key: value for key, value in agent_event.items() if key != "type"
                }
                yield _event(event_type, **event_data)
            yield _event("done")
        except Exception:
            logger.exception("chat_stream_failed", extra={"thread_id": str(payload.thread_id)})
            yield _event(
                "error",
                message="处理请求时出现问题，请稍后重试或换一种描述。",
            )

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
