from fastapi import APIRouter, HTTPException, status

from backend.app.agent.recipes import (
    RecipeOperationError,
    RecipeSearchError,
    RecipeSearchUnavailableError,
)
from backend.app.api.dependencies import RecipeAgentDependency
from backend.app.schemas.recipes import RecipeRequest, RecipeResponse

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("/recommend", response_model=RecipeResponse)
def recommend_recipe(
    payload: RecipeRequest,
    agent: RecipeAgentDependency,
) -> RecipeResponse:
    try:
        decision, recommendation = agent.recommend(
            message=payload.message,
            ingredients=payload.ingredients,
            image_context=payload.image_context,
            thread_id=payload.thread_id,
        )
    except RecipeSearchUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tavily search is required for this request but is not configured",
        ) from exc
    except RecipeSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Tavily search failed; verify TAVILY_API_KEY and service access",
        ) from exc
    except RecipeOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Recipe recommendation failed",
        ) from exc

    return RecipeResponse(
        thread_id=payload.thread_id,
        tool_used="tavily" if decision.use_tavily else "none",
        tool_reason=decision.reason,
        search_query=decision.search_query,
        recommendation=recommendation,
    )
