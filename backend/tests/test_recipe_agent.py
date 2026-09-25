from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from backend.app.agent.recipes import (
    RecipeAgent,
    RecipeSearchError,
    RecipeSearchUnavailableError,
    create_tavily_search_tool,
)
from backend.app.core.config import Settings
from backend.app.schemas.recipes import (
    RecipeImageContext,
    RecipeIngredient,
    RecipeIngredientInput,
    RecipeRecommendation,
    RecipeToolDecision,
    RecommendedRecipe,
)


def recommendation(source_urls: list[str] | None = None) -> RecipeRecommendation:
    return RecipeRecommendation(
        summary="根据现有食材推荐一道快手菜。",
        needs_clarification=False,
        recipes=[
            RecommendedRecipe(
                title="西红柿炒鸡蛋",
                rationale="食材齐全，适合快速制作。",
                servings="2人份",
                total_time_minutes=15,
                difficulty="简单",
                ingredients=[
                    RecipeIngredient(name="西红柿", amount="2个"),
                    RecipeIngredient(name="鸡蛋", amount="3个"),
                ],
                steps=["鸡蛋打散炒熟。", "下西红柿炒软后混合调味。"],
                substitutions=[],
                tips=["鸡蛋刚凝固就盛出。"],
                source_urls=source_urls or [],
            )
        ],
        safety_note="鸡蛋需充分加热。",
    )


class FakeStructuredModel:
    def __init__(self, result):
        self.result = result
        self.messages = None

    def invoke(self, messages, config=None):
        self.messages = messages
        return self.result


class FakeModel:
    def __init__(self, decision: RecipeToolDecision, result: RecipeRecommendation):
        self.decision_model = FakeStructuredModel(decision)
        self.recipe_model = FakeStructuredModel(result)
        self.stream_chunks: list[str] = []

    def with_structured_output(self, schema, **_):
        if schema is RecipeToolDecision:
            return self.decision_model
        if schema is RecipeRecommendation:
            return self.recipe_model
        raise AssertionError(f"Unexpected schema: {schema}")

    def stream(self, messages, config=None):
        for content in self.stream_chunks:
            yield SimpleNamespace(content=content)


class FakeSearchTool:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def invoke(self, input, config=None):
        self.queries.append(input["query"])
        return {
            "results": [
                {
                    "title": "参考菜谱",
                    "url": "https://example.com/recipe",
                    "content": "一份参考做法。",
                }
            ]
        }


class FailingSearchTool:
    def invoke(self, input, config=None):
        return {"error": ValueError("Unauthorized")}


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        dashscope_api_key=SecretStr("test-key"),
        checkpoint_sqlite_path=Path("ignored.sqlite"),
    )


def test_tavily_tool_uses_key_from_settings() -> None:
    settings = make_settings()
    settings.tavily_api_key = SecretStr("tvly-dev-test-key")

    tool = create_tavily_search_tool(settings)

    assert tool is not None
    assert tool.api_wrapper.tavily_api_key.get_secret_value() == "tvly-dev-test-key"


def test_recipe_agent_skips_search_for_normal_home_cooking() -> None:
    model = FakeModel(
        RecipeToolDecision(use_tavily=False, reason="常见家常菜无需搜索", search_query=""),
        recommendation(),
    )
    agent = RecipeAgent(make_settings(), InMemorySaver(), model=model)
    thread_id = uuid4()

    decision, result = agent.recommend(
        message="用西红柿和鸡蛋做一道快手菜",
        ingredients=[RecipeIngredientInput(name="西红柿", quantity="2个")],
        thread_id=thread_id,
    )

    assert decision.use_tavily is False
    assert result.recipes[0].title == "西红柿炒鸡蛋"
    snapshot = agent.graph.get_state(
        {"configurable": {"thread_id": f"{thread_id}:recipes"}}
    )
    assert len(snapshot.values["messages"]) == 2


def test_recipe_agent_calls_tavily_when_selected() -> None:
    search_tool = FakeSearchTool()
    model = FakeModel(
        RecipeToolDecision(
            use_tavily=True,
            reason="用户要求搜索来源",
            search_query="西红柿炒鸡蛋 菜谱 来源",
        ),
        recommendation(),
    )
    agent = RecipeAgent(
        make_settings(),
        InMemorySaver(),
        model=model,
        search_tool=search_tool,
    )

    decision, result = agent.recommend(
        message="搜索一份带来源的做法",
        ingredients=[],
        thread_id=uuid4(),
    )

    assert decision.use_tavily is True
    assert search_tool.queries == ["西红柿炒鸡蛋 菜谱 来源"]
    assert result.recipes[0].source_urls == ["https://example.com/recipe"]


def test_recipe_agent_streams_each_model_chunk_and_checkpoints_full_text() -> None:
    model = FakeModel(
        RecipeToolDecision(use_tavily=False, reason="无需搜索", search_query=""),
        recommendation(),
    )
    model.stream_chunks = ["第一段", "，第二段", "。"]
    agent = RecipeAgent(make_settings(), InMemorySaver(), model=model)
    thread_id = uuid4()

    events = list(
        agent.stream_recommendation(
            message="推荐一道菜",
            ingredients=[RecipeIngredientInput(name="鸡蛋", quantity="2个")],
            thread_id=thread_id,
        )
    )

    assert [event["content"] for event in events if event["type"] == "delta"] == [
        "第一段",
        "，第二段",
        "。",
    ]
    snapshot = agent.streaming_graph.get_state(
        {"configurable": {"thread_id": f"{thread_id}:recipes"}}
    )
    assert snapshot.values["messages"][-1]["content"] == "第一段，第二段。"


def test_recipe_agent_does_not_reuse_old_ingredients_for_non_food_image() -> None:
    model = FakeModel(
        RecipeToolDecision(use_tavily=False, reason="不会调用", search_query=""),
        recommendation(),
    )
    agent = RecipeAgent(make_settings(), InMemorySaver(), model=model)
    thread_id = uuid4()

    agent.recommend(
        message="用腐竹和木耳推荐一道菜",
        ingredients=[RecipeIngredientInput(name="腐竹"), RecipeIngredientInput(name="木耳")],
        thread_id=thread_id,
    )
    decision, result = agent.recommend(
        message="刚才的图片能做什么菜",
        ingredients=[],
        image_context=RecipeImageContext(
            is_food_image=False,
            summary="图片中是一只狗，没有可见食材。",
        ),
        thread_id=thread_id,
    )

    assert decision.use_tavily is False
    assert result.needs_clarification is True
    assert result.recipes == []
    assert "没有识别到" in result.summary


def test_recipe_agent_reports_missing_tavily_configuration() -> None:
    model = FakeModel(
        RecipeToolDecision(
            use_tavily=True,
            reason="用户要求最新资料",
            search_query="最新食品安全通告",
        ),
        recommendation(),
    )
    agent = RecipeAgent(make_settings(), InMemorySaver(), model=model)

    with pytest.raises(RecipeSearchUnavailableError, match="TAVILY_API_KEY"):
        agent.recommend(message="查找最新通告", ingredients=[], thread_id=uuid4())


def test_recipe_agent_reports_tavily_api_failure() -> None:
    model = FakeModel(
        RecipeToolDecision(
            use_tavily=True,
            reason="用户要求搜索",
            search_query="家常菜谱来源",
        ),
        recommendation(),
    )
    agent = RecipeAgent(
        make_settings(),
        InMemorySaver(),
        model=model,
        search_tool=FailingSearchTool(),
    )

    with pytest.raises(RecipeSearchError, match="Tavily search request failed"):
        agent.recommend(message="请搜索来源", ingredients=[], thread_id=uuid4())
