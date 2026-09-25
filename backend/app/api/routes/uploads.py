from fastapi import APIRouter, HTTPException, status

from backend.app.api.dependencies import OSSServiceDependency
from backend.app.schemas.uploads import (
    UploadCompleteRequest,
    UploadCompleteResponse,
    UploadPresignRequest,
    UploadPresignResponse,
)
from backend.app.services.oss_service import (
    InvalidUploadError,
    OSSConfigurationError,
    OSSOperationError,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/presign",
    response_model=UploadPresignResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_upload_url(
    payload: UploadPresignRequest,
    oss_service: OSSServiceDependency,
) -> UploadPresignResponse:
    try:
        ticket = oss_service.create_upload_url(
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except InvalidUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except OSSConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OSS storage is not configured",
        ) from exc
    except OSSOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create an upload URL",
        ) from exc

    return UploadPresignResponse(
        object_key=ticket.object_key,
        upload_url=ticket.upload_url,
        headers=ticket.signed_headers,
        expires_at=ticket.expires_at,
    )


@router.post("/complete", response_model=UploadCompleteResponse)
def complete_upload(
    payload: UploadCompleteRequest,
    oss_service: OSSServiceDependency,
) -> UploadCompleteResponse:
    try:
        uploaded = oss_service.verify_uploaded_image(payload.object_key)
    except InvalidUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except OSSConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OSS storage is not configured",
        ) from exc
    except OSSOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to verify the uploaded image",
        ) from exc

    return UploadCompleteResponse(
        object_key=uploaded.object_key,
        content_type=uploaded.content_type,
        size_bytes=uploaded.size_bytes,
    )
