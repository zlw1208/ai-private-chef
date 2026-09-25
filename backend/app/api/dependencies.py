from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status

from backend.app.agent.recipes import (
    RecipeAgent,
    RecipeConfigurationError,
    create_tavily_search_tool,
)
from backend.app.agent.recognition import (
    RecognitionAgent,
    RecognitionConfigurationError,
)
from backend.app.core.checkpoints import CheckpointManager
from backend.app.core.config import Settings, get_settings
from backend.app.services.oss_service import OSSConfigurationError, OSSService

SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_oss_service(settings: SettingsDependency) -> OSSService:
    try:
        return OSSService(settings)
    except OSSConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OSS storage is not configured",
        ) from exc


OSSServiceDependency = Annotated[OSSService, Depends(get_oss_service)]


@lru_cache
def get_checkpoint_manager() -> CheckpointManager:
    return CheckpointManager(get_settings())


def get_checkpointer():
    return get_checkpoint_manager().open()


def initialize_dependencies() -> None:
    get_checkpointer()


def close_dependencies() -> None:
    get_recipe_agent.cache_clear()
    get_checkpoint_manager().close()
    get_checkpoint_manager.cache_clear()


def get_recognition_agent(
    settings: SettingsDependency,
    oss_service: OSSServiceDependency,
) -> RecognitionAgent:
    try:
        return RecognitionAgent(
            settings,
            oss_service,
            get_checkpointer(),
        )
    except RecognitionConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Multimodal recognition is not configured",
        ) from exc


RecognitionAgentDependency = Annotated[RecognitionAgent, Depends(get_recognition_agent)]


@lru_cache
def get_recipe_agent() -> RecipeAgent:
    settings = get_settings()
    try:
        return RecipeAgent(
            settings,
            get_checkpointer(),
            search_tool=create_tavily_search_tool(settings),
        )
    except RecipeConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recipe recommendation is not configured",
        ) from exc


RecipeAgentDependency = Annotated[RecipeAgent, Depends(get_recipe_agent)]
