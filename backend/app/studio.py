"""LangSmith Studio graph exports."""

import base64
import binascii
from functools import lru_cache
from typing import Any
from uuid import UUID, uuid4

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph

from backend.app.agent.recipes import RecipeAgent, create_tavily_search_tool
from backend.app.agent.recognition import RecognitionAgent
from backend.app.core.config import get_settings
from backend.app.core.observability import configure_langsmith
from backend.app.services.oss_service import InvalidUploadError, OSSService


class StudioRecipeState(MessagesState, total=False):
    """Chat-compatible recipe state exposed to LangSmith Studio."""

    user_message: str
    ingredients: list[dict[str, str]]
    image_context: dict[str, Any] | None
    image_object_key: str | None
    tool_decision: dict[str, Any]
    search_results: list[dict[str, str]]


def _message_content(message: BaseMessage | dict[str, Any]) -> str:
    content = message.content if isinstance(message, BaseMessage) else message.get("content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def _message_role(message: BaseMessage | dict[str, Any]) -> str:
    if isinstance(message, dict):
        return str(message.get("role", "user"))
    return {
        "human": "user",
        "ai": "assistant",
    }.get(message.type, message.type)


def _message_blocks(message: BaseMessage | dict[str, Any]) -> list[dict[str, Any]]:
    content = message.content if isinstance(message, BaseMessage) else message.get("content", [])
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _decode_studio_image(block: dict[str, Any], *, max_size_bytes: int) -> tuple[bytes, str]:
    """Decode Studio's standard base64 image content block with a strict size cap."""
    if block.get("type") != "image" or block.get("source_type") != "base64":
        raise InvalidUploadError("Studio image attachment must use base64 image data")

    content_type = str(block.get("mime_type", "")).strip().lower()
    encoded = block.get("data")
    if not isinstance(encoded, str) or not encoded:
        raise InvalidUploadError("Studio image attachment is empty")
    if encoded.startswith("data:"):
        _, separator, encoded = encoded.partition(",")
        if not separator:
            raise InvalidUploadError("Studio image attachment is invalid")

    # Base64 is roughly 4/3 the decoded size. Reject oversized input before allocating it.
    if len(encoded) > ((max_size_bytes + 2) // 3) * 4 + 4:
        raise InvalidUploadError("Studio image attachment exceeds the configured size limit")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidUploadError("Studio image attachment is not valid base64") from exc
    if len(data) > max_size_bytes:
        raise InvalidUploadError("Studio image attachment exceeds the configured size limit")
    return data, content_type


def _recipe_state(state: StudioRecipeState) -> dict[str, Any]:
    messages = [
        {"role": _message_role(message), "content": _message_content(message)}
        for message in state.get("messages", [])
    ]
    return {
        "user_message": state["user_message"],
        "ingredients": state.get("ingredients", []),
        "image_context": state.get("image_context"),
        "messages": messages,
        "tool_decision": state.get("tool_decision"),
        "search_results": state.get("search_results", []),
    }


settings = get_settings()
configure_langsmith(settings)


@lru_cache
def _get_oss_service() -> OSSService:
    return OSSService(settings)


@lru_cache
def _get_recognition_agent() -> RecognitionAgent:
    return RecognitionAgent(settings, _get_oss_service(), checkpointer=None)


@lru_cache
def _get_recipe_agent() -> RecipeAgent:
    return RecipeAgent(
        settings,
        checkpointer=None,
        search_tool=create_tavily_search_tool(settings),
    )


def prepare_request(state: StudioRecipeState) -> dict[str, Any]:
    for message in reversed(state.get("messages", [])):
        if _message_role(message) == "user":
            content = _message_content(message).strip()
            image_blocks = [
                block for block in _message_blocks(message) if block.get("type") == "image"
            ]
            if image_blocks:
                if len(image_blocks) > 1:
                    raise InvalidUploadError("Studio currently supports one image per message")
                data, content_type = _decode_studio_image(
                    image_blocks[0],
                    max_size_bytes=settings.oss_max_image_size_bytes,
                )
                uploaded = _get_oss_service().upload_image_bytes(
                    data=data,
                    content_type=content_type,
                )
                return {
                    "user_message": content or "请根据这张图片中的食材推荐菜谱",
                    "ingredients": [],
                    "image_context": None,
                    "image_object_key": uploaded.object_key,
                    "search_results": [],
                }
            if content:
                return {
                    "user_message": content,
                    "ingredients": state.get("ingredients", []),
                    "image_context": state.get("image_context"),
                    "image_object_key": None,
                    "search_results": [],
                }
    raise ValueError("Studio Chat requires text or an image")


def recognize_image(
    state: StudioRecipeState,
    config: RunnableConfig,
) -> dict[str, Any]:
    object_key = state.get("image_object_key")
    if not object_key:
        raise ValueError("Studio image object key is missing")

    raw_thread_id = config.get("configurable", {}).get("thread_id")
    try:
        thread_id = UUID(str(raw_thread_id))
    except (TypeError, ValueError, AttributeError):
        thread_id = uuid4()
    result = _get_recognition_agent().recognize(
        object_key=object_key,
        thread_id=thread_id,
        user_text=state.get("user_message", ""),
    )
    return {
        "ingredients": [
            {
                "name": ingredient.name_zh,
                "quantity": ingredient.quantity_estimate,
                "state": ingredient.visible_state,
            }
            for ingredient in result.ingredients
        ],
        "image_context": {
            "is_food_image": result.is_food_image,
            "summary": result.summary,
        },
    }


def route_after_prepare(state: StudioRecipeState) -> str:
    return "recognize" if state.get("image_object_key") else "decide"


def decide_tool(state: StudioRecipeState) -> dict[str, Any]:
    return _get_recipe_agent()._decide_tool_stream(_recipe_state(state))


def search_web(state: StudioRecipeState) -> dict[str, Any]:
    return _get_recipe_agent()._search_web_stream(_recipe_state(state))


def generate_recipe(state: StudioRecipeState) -> dict[str, Any]:
    return _get_recipe_agent()._generate_recipe_stream(_recipe_state(state))


def route_after_decision(state: StudioRecipeState) -> str:
    return _get_recipe_agent()._route_after_decision(
        {"tool_decision": state["tool_decision"]}
    )


builder = StateGraph(StudioRecipeState)
builder.add_node("prepare_request", prepare_request)
builder.add_node("recognize_image", recognize_image)
builder.add_node("decide_tool", decide_tool)
builder.add_node("search_web", search_web)
builder.add_node("generate_recipe", generate_recipe)
builder.add_edge(START, "prepare_request")
builder.add_conditional_edges(
    "prepare_request",
    route_after_prepare,
    {"recognize": "recognize_image", "decide": "decide_tool"},
)
builder.add_edge("recognize_image", "decide_tool")
builder.add_conditional_edges(
    "decide_tool",
    route_after_decision,
    {"search": "search_web", "generate": "generate_recipe"},
)
builder.add_edge("search_web", "generate_recipe")
builder.add_edge("generate_recipe", END)

# Agent Server supplies the checkpointer for Studio threads.
recipe_graph = builder.compile()
