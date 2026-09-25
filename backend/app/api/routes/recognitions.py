from fastapi import APIRouter, HTTPException, status

from backend.app.agent.recognition import (
    RecognitionConfigurationError,
    RecognitionOperationError,
)
from backend.app.api.dependencies import RecognitionAgentDependency
from backend.app.schemas.recognition import RecognitionRequest, RecognitionResponse
from backend.app.services.oss_service import InvalidUploadError, OSSOperationError

router = APIRouter(prefix="/recognitions", tags=["recognitions"])


@router.post("", response_model=RecognitionResponse)
def recognize_ingredients(
    payload: RecognitionRequest,
    agent: RecognitionAgentDependency,
) -> RecognitionResponse:
    try:
        recognition = agent.recognize(
            object_key=payload.object_key,
            thread_id=payload.thread_id,
            user_text=payload.user_text,
        )
    except InvalidUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RecognitionConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Multimodal recognition is not configured",
        ) from exc
    except OSSOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to access the uploaded image",
        ) from exc
    except RecognitionOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ingredient recognition failed",
        ) from exc

    return RecognitionResponse(
        thread_id=payload.thread_id,
        object_key=payload.object_key,
        recognition=recognition,
    )

