from operator import add
from typing import Annotated, Any, TypedDict


class RecipeState(TypedDict, total=False):
    user_message: str
    ingredients: list[dict[str, str]]
    image_context: dict[str, Any] | None
    messages: Annotated[list[dict[str, str]], add]
    tool_decision: dict[str, Any]
    search_results: list[dict[str, str]]
    recommendation: dict[str, Any]
