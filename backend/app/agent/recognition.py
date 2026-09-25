from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from backend.app.agent.prompts import INGREDIENT_RECOGNITION_SYSTEM_PROMPT
from backend.app.agent.state import RecognitionState
from backend.app.core.config import Settings
from backend.app.schemas.recognition import IngredientRecognition
from backend.app.services.oss_service import InvalidUploadError, OSSOperationError, OSSService


class RecognitionConfigurationError(RuntimeError):
    """Raised when the recognition agent is not configured."""


class RecognitionOperationError(RuntimeError):
    """Raised when the recognition workflow fails."""
class RecognitionAgent:
    def __init__(
        self,
        settings: Settings,
        oss_service: OSSService,
        checkpointer: BaseCheckpointSaver[str] | None,
        *,
        model: Any | None = None,
    ) -> None:
        self._settings = settings
        self._oss_service = oss_service
        self._model = model or self._create_model(settings)
        self._structured_model = self._model.with_structured_output(
            IngredientRecognition,
            method="json_schema",
            strict=True,
        )
        self.graph = self._build_graph(checkpointer)

    @staticmethod
    def _create_model(settings: Settings) -> ChatOpenAI:
        if (
            settings.dashscope_api_key is None
            or not settings.dashscope_api_key.get_secret_value()
        ):
            raise RecognitionConfigurationError("DASHSCOPE_API_KEY is not configured")
        if not settings.dashscope_model.strip():
            raise RecognitionConfigurationError("DASHSCOPE_MODEL is not configured")
        return ChatOpenAI(
            model=settings.dashscope_model,
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            temperature=0,
            reasoning_effort=settings.qwen_reasoning_effort,
            max_retries=2,
            timeout=60,
        )

    def _build_graph(self, checkpointer: BaseCheckpointSaver[str] | None) -> Any:
        builder = StateGraph(RecognitionState)
        builder.add_node("prepare_image", self._prepare_image)
        builder.add_node("recognize_ingredients", self._recognize_ingredients)
        builder.add_edge(START, "prepare_image")
        builder.add_edge("prepare_image", "recognize_ingredients")
        builder.add_edge("recognize_ingredients", END)
        return builder.compile(checkpointer=checkpointer)

    def _prepare_image(self, state: RecognitionState) -> dict[str, str]:
        self._oss_service.verify_uploaded_image(state["object_key"])
        return {"object_key": state["object_key"]}

    def _recognize_ingredients(
        self,
        state: RecognitionState,
    ) -> dict[str, IngredientRecognition]:
        user_context = state.get("user_text", "").strip()
        text = "请识别图片中清晰可见的食材。"
        if user_context:
            text += f"\n用户补充说明：{user_context}"
        image_ticket = self._oss_service.create_model_download_url(state["object_key"])

        messages = [
            SystemMessage(content=INGREDIENT_RECOGNITION_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {"type": "text", "text": text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_ticket.download_url,
                        },
                        "max_pixels": self._settings.qwen_image_max_pixels,
                    },
                ]
            ),
        ]
        result = self._structured_model.invoke(
            messages,
            config={
                "run_name": "recognize-ingredients-model",
                "tags": ["ai-private-chef", "multimodal", "qwen"],
                "metadata": {
                    "feature": "ingredient_recognition",
                    "model": self._settings.dashscope_model,
                },
            },
        )
        if not isinstance(result, IngredientRecognition):
            result = IngredientRecognition.model_validate(result)
        # Persist only JSON-compatible primitives. Storing the Pydantic model itself
        # makes LangGraph checkpoints depend on importing an application class.
        return {"recognition": result.model_dump(mode="json")}

    def recognize(
        self,
        *,
        object_key: str,
        thread_id: UUID,
        user_text: str = "",
    ) -> IngredientRecognition:
        config = {
            "configurable": {"thread_id": str(thread_id)},
            "run_name": "ingredient-recognition-graph",
            "tags": ["ai-private-chef", "recognition", "langgraph"],
            "metadata": {
                "feature": "ingredient_recognition",
                "model": self._settings.dashscope_model,
                "thread_id": str(thread_id),
            },
        }
        try:
            result = self.graph.invoke(
                {"object_key": object_key, "user_text": user_text},
                config=config,
            )
        except (InvalidUploadError, OSSOperationError):
            raise
        except Exception as exc:
            raise RecognitionOperationError("Ingredient recognition failed") from exc

        recognition = result.get("recognition")
        if recognition is None:
            raise RecognitionOperationError("Recognition result was missing")
        if isinstance(recognition, IngredientRecognition):
            return recognition
        return IngredientRecognition.model_validate(recognition)
