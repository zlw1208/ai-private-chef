from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RecipeIngredientInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    quantity: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)


class RecipeImageContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_food_image: bool
    summary: str = Field(min_length=1, max_length=500)


class RecipeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    ingredients: list[RecipeIngredientInput] = Field(default_factory=list, max_length=50)
    image_context: RecipeImageContext | None = None
    thread_id: UUID = Field(default_factory=uuid4)


class RecipeToolDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_tavily: bool = Field(description="是否需要搜索实时或外部信息")
    reason: str = Field(description="简短解释为什么搜索或不搜索")
    search_query: str = Field(description="需要搜索时的中文查询，否则为空字符串")


class RecipeIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    amount: str


class RecommendedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    rationale: str
    servings: str
    total_time_minutes: int = Field(ge=1, le=1440)
    difficulty: Literal["简单", "中等", "较难"]
    ingredients: list[RecipeIngredient]
    steps: list[str] = Field(min_length=1)
    substitutions: list[str]
    tips: list[str]
    source_urls: list[str] = Field(
        description="仅在使用 Tavily 时填写搜索结果中的来源 URL"
    )


class RecipeRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    needs_clarification: bool
    recipes: list[RecommendedRecipe] = Field(max_length=3)
    safety_note: str


class RecipeResponse(BaseModel):
    thread_id: UUID
    tool_used: Literal["none", "tavily"]
    tool_reason: str
    search_query: str
    recommendation: RecipeRecommendation
