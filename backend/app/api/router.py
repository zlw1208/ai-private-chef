from fastapi import APIRouter

from backend.app.api.routes.admin import router as admin_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.recipes import router as recipes_router
from backend.app.api.routes.recognitions import router as recognitions_router
from backend.app.api.routes.uploads import router as uploads_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(chat_router)
api_router.include_router(uploads_router)
api_router.include_router(recognitions_router)
api_router.include_router(recipes_router)
