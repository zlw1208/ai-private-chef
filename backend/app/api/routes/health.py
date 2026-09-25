from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app import APP_VERSION
from backend.app.core.config import Settings, get_settings
from backend.app.schemas.health import HealthResponse, RootResponse

router = APIRouter(tags=["system"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/api/info", response_model=RootResponse)
async def service_info(settings: SettingsDependency) -> RootResponse:
    return RootResponse(
        name=settings.app_name,
        version=APP_VERSION,
        docs_url="/docs",
        health_url="/health",
    )


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        version=APP_VERSION,
        timestamp=datetime.now(UTC),
    )
