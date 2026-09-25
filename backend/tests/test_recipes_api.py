from uuid import UUID

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_recipe_agent
from backend.app.main import app
from backend.app.schemas.recipes import (
    RecipeIngredient,
    RecipeRecommendation,
    RecipeToolDecision,
    RecommendedRecipe,
)

THREAD_ID = "12345678-1234-1234-1234-123456789abc"


class StubRecipeAgent:
    def recommend(self, *, message: str, ingredients: list, image_context, thread_id: UUID):
        assert message == "推荐一道快手菜"
        assert ingredients[0].name == "鸡蛋"
        assert str(thread_id) == THREAD_ID
        assert image_context is None
        return (
            RecipeToolDecision(use_tavily=False, reason="无需搜索", search_query=""),
            RecipeRecommendation(
                summary="推荐番茄炒蛋。",
                needs_clarification=False,
                recipes=[
                    RecommendedRecipe(
                        title="番茄炒蛋",
                        rationale="快手",
                        servings="2人份",
                        total_time_minutes=15,
                        difficulty="简单",
                        ingredients=[RecipeIngredient(name="鸡蛋", amount="3个")],
                        steps=["炒熟。"],
                        substitutions=[],
                        tips=[],
                        source_urls=[],
                    )
                ],
                safety_note="充分加热。",
            ),
        )


def test_recommend_recipe_endpoint() -> None:
    app.dependency_overrides[get_recipe_agent] = lambda: StubRecipeAgent()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/recipes/recommend",
                json={
                    "message": "推荐一道快手菜",
                    "ingredients": [{"name": "鸡蛋", "quantity": "3个", "state": "新鲜"}],
                    "thread_id": THREAD_ID,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "none"
    assert payload["recommendation"]["recipes"][0]["title"] == "番茄炒蛋"
