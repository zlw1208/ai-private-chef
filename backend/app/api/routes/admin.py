from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from langgraph.checkpoint.base import BaseCheckpointSaver

from backend.app.api.dependencies import get_checkpointer
from backend.app.core.config import Settings, get_settings
from backend.app.core.local_access import require_local_access
from backend.app.schemas.admin import AdminOverview, AdminThreadDetail
from backend.app.services.admin_service import build_overview, build_thread_detail

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_local_access)],
)
SettingsDependency = Annotated[Settings, Depends(get_settings)]
CheckpointerDependency = Annotated[BaseCheckpointSaver[str], Depends(get_checkpointer)]


@router.get("/overview", response_model=AdminOverview)
def admin_overview(
    settings: SettingsDependency,
    checkpointer: CheckpointerDependency,
    scan_limit: int = Query(default=1000, ge=1, le=5000),
) -> AdminOverview:
    return build_overview(settings, checkpointer, scan_limit=scan_limit)


@router.get("/threads/{thread_id:path}", response_model=AdminThreadDetail)
def admin_thread_detail(
    thread_id: str,
    checkpointer: CheckpointerDependency,
) -> AdminThreadDetail:
    detail = build_thread_detail(checkpointer, thread_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found",
        )
    return detail
