from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UploadPresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)

    @field_validator("filename", "content_type")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class UploadPresignResponse(BaseModel):
    object_key: str
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_at: datetime


class UploadCompleteRequest(BaseModel):
    object_key: str = Field(min_length=1, max_length=512)


class UploadCompleteResponse(BaseModel):
    object_key: str
    content_type: str
    size_bytes: int
    status: Literal["verified"] = "verified"

