import json
import re
from collections.abc import Iterator
from typing import Any, Protocol
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from backend.app.agent.prompts import (
    RECIPE_RECOMMENDATION_SYSTEM_PROMPT,
    RECIPE_STREAM_SYSTEM_PROMPT,
    RECIPE_TOOL_DECISION_SYSTEM_PROMPT,
)
from backend.app.agent.recipe_state import RecipeState
from backend.app.core.config import Settings
from backend.app.schemas.recipes import (
    RecipeImageContext,
    RecipeIngredientInput,
    RecipeRecommendation,
    RecipeToolDecision,
)


class RecipeConfigurationError(RuntimeError):
    """Raised when the recipe agent model is not configured."""


class RecipeSearchUnavailableError(RuntimeError):
    """Raised when the agent selects Tavily but it is not configured."""


class RecipeSearchError(RuntimeError):
    """Raised when Tavily rejects or cannot complete a search."""


class RecipeOperationError(RuntimeError):
    """Raised when recipe generation fails."""


class SearchTool(Protocol):
    def invoke(self, input: dict[str, str], config: dict[str, Any] | None = None) -> Any: ...


def create_tavily_search_tool(settings: Settings) -> TavilySearch | None:
    if settings.tavily_api_key is None:
        return None
    api_key = settings.tavily_api_key.get_secret_value()
    if not api_key:
        return None
    return TavilySearch(
        tavily_api_key=api_key,
        max_results=5,
        search_depth="advanced",
        topic="general",
        include_answer=False,
        include_raw_content=False,
    )


class RecipeAgent:
    def __init__(
        self,
        settings: Settings,
        checkpointer: BaseCheckpointSaver[str] | None,
        *,
        model: Any | None = None,
        search_tool: SearchTool | None = None,
    ) -> None:
        self._model = model or self._create_model(settings)
        self._decision_model = self._model.with_structured_output(
            RecipeToolDecision,
            method="json_schema",
            strict=True,
        )
        self._recipe_model = self._model.with_structured_output(
            RecipeRecommendation,
            method="json_schema",
            strict=True,
        )
        self._search_tool = search_tool
        self.graph = self._build_graph(checkpointer)
        self.streaming_graph = self._build_streaming_graph(checkpointer)

    @staticmethod
    def _create_model(settings: Settings) -> ChatOpenAI:
        if (
            settings.dashscope_api_key is None
            or not settings.dashscope_api_key.get_secret_value()
        ):
            raise RecipeConfigurationError("DASHSCOPE_API_KEY is not configured")
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
        builder = StateGraph(RecipeState)
        builder.add_node("decide_tool", self._decide_tool)
        builder.add_node("search_web", self._search_web)
        builder.add_node("generate_recipe", self._generate_recipe)
        builder.add_edge(START, "decide_tool")
        builder.add_conditional_edges(
            "decide_tool",
            self._route_after_decision,
            {"search": "search_web", "generate": "generate_recipe"},
        )
        builder.add_edge("search_web", "generate_recipe")
        builder.add_edge("generate_recipe", END)
        return builder.compile(checkpointer=checkpointer)

    def _build_streaming_graph(self, checkpointer: BaseCheckpointSaver[str] | None) -> Any:
        builder = StateGraph(RecipeState)
        builder.add_node("decide_tool", self._decide_tool_stream)
        builder.add_node("search_web", self._search_web_stream)
        builder.add_node("generate_recipe", self._generate_recipe_stream)
        builder.add_edge(START, "decide_tool")
        builder.add_conditional_edges(
            "decide_tool",
            self._route_after_decision,
            {"search": "search_web", "generate": "generate_recipe"},
        )
        builder.add_edge("search_web", "generate_recipe")
        builder.add_edge("generate_recipe", END)
        return builder.compile(checkpointer=checkpointer)

    def _decide_tool_stream(self, state: RecipeState) -> dict[str, dict[str, Any]]:
        result = self._decide_tool(state)
        decision = RecipeToolDecision.model_validate(result["tool_decision"])
        get_stream_writer()(
            {
                "type": "meta",
                "tool_used": "tavily" if decision.use_tavily else "none",
                "tool_reason": decision.reason,
            }
        )
        return result

    def _search_web_stream(self, state: RecipeState) -> dict[str, list[dict[str, str]]]:
        get_stream_writer()({"type": "status", "message": "正在通过 Tavily 查找资料…"})
        return self._search_web(state)

    def _generate_recipe_stream(self, state: RecipeState) -> dict[str, Any]:
        writer = get_stream_writer()
        if self._needs_image_clarification(state):
            content = (
                "刚才的图片中没有识别到可用于烹饪的食材。"
                "请上传一张食材照片，或直接告诉我你现有的食材。\n\n"
                "安全提示：请勿将宠物或其他非食物对象作为食材处理。"
            )
            writer({"type": "delta", "content": content})
            return {"messages": [{"role": "assistant", "content": content}]}

        payload = {
            "request": state["user_message"],
            "ingredients": state.get("ingredients", []),
            "current_image": state.get("image_context"),
            "recent_conversation": self._recent_conversation(state),
            "tavily_results": state.get("search_results", []),
        }
        writer({"type": "status", "message": "正在为你设计菜谱…"})
        chunks: list[str] = []
        for chunk in self._model.stream(
            [
                SystemMessage(content=RECIPE_STREAM_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
            config={
                "run_name": "stream-recipe-model",
                "tags": ["ai-private-chef", "recipe-generation", "qwen", "streaming"],
                "metadata": {"feature": "recipe_generation_stream"},
            },
        ):
            content = self._chunk_text(chunk.content)
            if not content:
                continue
            chunks.append(content)
            writer({"type": "delta", "content": content})
        complete_text = "".join(chunks)
        if not complete_text:
            raise RecipeOperationError("Streaming recipe response was empty")
        return {"messages": [{"role": "assistant", "content": complete_text}]}

    @staticmethod
    def _chunk_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)

    def _decide_tool(self, state: RecipeState) -> dict[str, dict[str, Any]]:
        if self._needs_image_clarification(state):
            decision = RecipeToolDecision(
                use_tavily=False,
                reason="当前图片不是食物，需先获得有效食材信息",
                search_query="",
            )
            return {"tool_decision": decision.model_dump(mode="json")}
        payload = {
            "request": state["user_message"],
            "ingredients": state.get("ingredients", []),
            "current_image": state.get("image_context"),
            "recent_conversation": self._recent_conversation(state),
        }
        result = self._decision_model.invoke(
            [
                SystemMessage(content=RECIPE_TOOL_DECISION_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
            config={
                "run_name": "decide-recipe-tool",
                "tags": ["ai-private-chef", "tool-routing", "qwen"],
                "metadata": {"feature": "recipe_tool_decision"},
            },
        )
        if not isinstance(result, RecipeToolDecision):
            result = RecipeToolDecision.model_validate(result)
        if not result.use_tavily:
            result.search_query = ""
        return {"tool_decision": result.model_dump(mode="json")}

    @staticmethod
    def _route_after_decision(state: RecipeState) -> str:
        decision = RecipeToolDecision.model_validate(state["tool_decision"])
        return "search" if decision.use_tavily else "generate"

    def _search_web(self, state: RecipeState) -> dict[str, list[dict[str, str]]]:
        if self._search_tool is None:
            raise RecipeSearchUnavailableError("TAVILY_API_KEY is not configured")
        decision = RecipeToolDecision.model_validate(state["tool_decision"])
        raw_result = self._search_tool.invoke(
            {"query": decision.search_query},
            config={
                "run_name": "search-recipes-tavily",
                "tags": ["ai-private-chef", "tool", "tavily"],
                "metadata": {"feature": "recipe_web_search"},
            },
        )
        if isinstance(raw_result, dict) and raw_result.get("error"):
            raise RecipeSearchError("Tavily search request failed")
        return {"search_results": self._normalize_search_results(raw_result)}

    @staticmethod
    def _normalize_search_results(raw_result: Any) -> list[dict[str, str]]:
        if isinstance(raw_result, dict):
            candidates = raw_result.get("results", [])
        elif isinstance(raw_result, list):
            candidates = raw_result
        else:
            candidates = []
        normalized = []
        for item in candidates[:5]:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "content": str(item.get("content", item.get("snippet", "")))[:2000],
                }
            )
        return normalized

    def _generate_recipe(self, state: RecipeState) -> dict[str, Any]:
        if self._needs_image_clarification(state):
            result = RecipeRecommendation(
                summary=(
                    "刚才的图片中没有识别到可用于烹饪的食材。"
                    "请上传一张食材照片，或直接告诉我你现有的食材。"
                ),
                needs_clarification=True,
                recipes=[],
                safety_note="请勿将宠物或其他非食物对象作为食材处理。",
            )
            return {
                "recommendation": result.model_dump(mode="json"),
                "messages": [{"role": "assistant", "content": result.model_dump_json()}],
            }
        payload = {
            "request": state["user_message"],
            "ingredients": state.get("ingredients", []),
            "current_image": state.get("image_context"),
            "recent_conversation": self._recent_conversation(state),
            "tavily_results": state.get("search_results", []),
        }
        result = self._recipe_model.invoke(
            [
                SystemMessage(content=RECIPE_RECOMMENDATION_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
            config={
                "run_name": "generate-recipe-model",
                "tags": ["ai-private-chef", "recipe-generation", "qwen"],
                "metadata": {"feature": "recipe_generation"},
            },
        )
        if not isinstance(result, RecipeRecommendation):
            result = RecipeRecommendation.model_validate(result)
        allowed_urls = [
            item["url"]
            for item in state.get("search_results", [])
            if item.get("url", "").startswith(("http://", "https://"))
        ]
        for recipe in result.recipes:
            recipe.source_urls = [url for url in recipe.source_urls if url in allowed_urls]
            if allowed_urls and not recipe.source_urls:
                recipe.source_urls = allowed_urls[:2]
        result_data = result.model_dump(mode="json")
        return {
            "recommendation": result_data,
            "messages": [
                {
                    "role": "assistant",
                    "content": result.model_dump_json(),
                }
            ],
        }

    @staticmethod
    def _recent_conversation(state: RecipeState) -> list[dict[str, str]]:
        # Uploading a new image starts a new ingredient context. Old messages remain
        # checkpointed for auditability but must not override the latest visual result.
        if state.get("image_context") is not None:
            return []
        return state.get("messages", [])[-6:]

    @staticmethod
    def _needs_image_clarification(state: RecipeState) -> bool:
        image_context = state.get("image_context")
        if not image_context or image_context.get("is_food_image", True):
            return False
        if state.get("ingredients"):
            return False
        return re.search(
            r"(刚才|这张|上面|上传).{0,8}(图片|照片)|图片|照片",
            state.get("user_message", ""),
            flags=re.IGNORECASE,
        ) is not None

    def recommend(
        self,
        *,
        message: str,
        ingredients: list[RecipeIngredientInput],
        image_context: RecipeImageContext | None = None,
        thread_id: UUID,
    ) -> tuple[RecipeToolDecision, RecipeRecommendation]:
        config = {
            "configurable": {
                "thread_id": f"{thread_id}:recipes",
            },
            "run_name": "recipe-recommendation-graph",
            "tags": ["ai-private-chef", "recipes", "langgraph"],
            "metadata": {
                "feature": "recipe_recommendation",
                "thread_id": str(thread_id),
            },
        }
        ingredient_data = [ingredient.model_dump(mode="json") for ingredient in ingredients]
        image_context_data = (
            image_context.model_dump(mode="json") if image_context is not None else None
        )
        try:
            result = self.graph.invoke(
                {
                    "user_message": message,
                    "ingredients": ingredient_data,
                    "image_context": image_context_data,
                    "messages": [{"role": "user", "content": message}],
                    "search_results": [],
                },
                config=config,
            )
        except RecipeSearchUnavailableError:
            raise
        except RecipeSearchError:
            raise
        except Exception as exc:
            raise RecipeOperationError("Recipe recommendation failed") from exc

        decision = RecipeToolDecision.model_validate(result.get("tool_decision"))
        recommendation = RecipeRecommendation.model_validate(result.get("recommendation"))
        return decision, recommendation

    def stream_recommendation(
        self,
        *,
        message: str,
        ingredients: list[RecipeIngredientInput],
        image_context: RecipeImageContext | None = None,
        thread_id: UUID,
    ) -> Iterator[dict[str, Any]]:
        config = {
            "configurable": {"thread_id": f"{thread_id}:recipes"},
            "run_name": "recipe-recommendation-streaming-graph",
            "tags": ["ai-private-chef", "recipes", "langgraph", "streaming"],
            "metadata": {
                "feature": "recipe_recommendation_stream",
                "thread_id": str(thread_id),
            },
        }
        ingredient_data = [ingredient.model_dump(mode="json") for ingredient in ingredients]
        image_context_data = (
            image_context.model_dump(mode="json") if image_context is not None else None
        )
        try:
            yield from self.streaming_graph.stream(
                {
                    "user_message": message,
                    "ingredients": ingredient_data,
                    "image_context": image_context_data,
                    "messages": [{"role": "user", "content": message}],
                    "search_results": [],
                },
                config=config,
                stream_mode="custom",
            )
        except (RecipeSearchUnavailableError, RecipeSearchError, RecipeOperationError):
            raise
        except Exception as exc:
            raise RecipeOperationError("Streaming recipe recommendation failed") from exc
