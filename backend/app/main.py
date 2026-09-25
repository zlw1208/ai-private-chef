from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app import APP_VERSION
from backend.app.api.dependencies import close_dependencies, initialize_dependencies
from backend.app.api.router import api_router
from backend.app.api.routes.health import router as system_router
from backend.app.core.config import get_settings
from backend.app.core.local_access import require_local_access
from backend.app.core.logging import configure_logging, get_logger
from backend.app.core.middleware import RequestContextMiddleware
from backend.app.core.observability import configure_langsmith

settings = get_settings()
configure_logging(settings.log_level)
configure_langsmith(settings)
logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_dependencies()
    logger.info(
        "application_started",
        extra={
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "version": APP_VERSION,
        },
    )
    try:
        yield
    finally:
        close_dependencies()
        logger.info("application_stopped")


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_ROOT / "assets"),
        name="assets",
    )

    @application.get("/", include_in_schema=False)
    async def frontend() -> FileResponse:
        return FileResponse(FRONTEND_ROOT / "index.html")

    @application.get(
        "/admin",
        include_in_schema=False,
        dependencies=[Depends(require_local_access)],
    )
    async def admin_frontend() -> FileResponse:
        return FileResponse(FRONTEND_ROOT / "admin.html")

    application.include_router(system_router)
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_app()
