import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import alibabacloud_oss_v2 as oss

from backend.app.core.config import Settings

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
UPLOAD_KEY_PATTERN = re.compile(
    r"^uploads/\d{4}/\d{2}/\d{2}/[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:jpg|png|webp)$"
)


class OSSServiceError(RuntimeError):
    """Base error raised by the OSS integration."""


class OSSConfigurationError(OSSServiceError):
    """Raised when required OSS configuration is missing."""


class InvalidUploadError(OSSServiceError):
    """Raised when an image upload violates application constraints."""


class OSSOperationError(OSSServiceError):
    """Raised when an OSS request fails."""


@dataclass(frozen=True)
class PresignedUpload:
    object_key: str
    upload_url: str
    signed_headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class VerifiedUpload:
    object_key: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class PresignedDownload:
    object_key: str
    download_url: str
    expires_at: datetime


class OSSService:
    def __init__(
        self,
        settings: Settings,
        *,
        client: oss.Client | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._now = now or (lambda: datetime.now(UTC))
        self._bucket = self._require_text("OSS_BUCKET", settings.oss_bucket)

        if client is not None:
            self._client = client
            return

        region = self._require_text("OSS_REGION", settings.oss_region)
        endpoint = self._require_text("OSS_ENDPOINT", settings.oss_endpoint)
        access_key_id = self._require_secret("OSS_ACCESS_KEY_ID", settings.oss_access_key_id)
        access_key_secret = self._require_secret(
            "OSS_ACCESS_KEY_SECRET", settings.oss_access_key_secret
        )

        provider = oss.credentials.StaticCredentialsProvider(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )
        config = oss.config.load_default()
        config.credentials_provider = provider
        config.region = region
        config.endpoint = endpoint
        self._client = oss.Client(config)

    @staticmethod
    def _require_text(name: str, value: str | None) -> str:
        if value is None or not value.strip():
            raise OSSConfigurationError(f"{name} is not configured")
        return value.strip()

    @staticmethod
    def _require_secret(name: str, value: object | None) -> str:
        if value is None or not hasattr(value, "get_secret_value"):
            raise OSSConfigurationError(f"{name} is not configured")
        secret = value.get_secret_value()
        if not secret:
            raise OSSConfigurationError(f"{name} is not configured")
        return secret

    @staticmethod
    def normalize_content_type(content_type: str) -> str:
        return content_type.split(";", maxsplit=1)[0].strip().lower()

    def validate_upload_request(self, content_type: str, size_bytes: int) -> str:
        normalized_type = self.normalize_content_type(content_type)
        if normalized_type not in SUPPORTED_IMAGE_TYPES:
            allowed = ", ".join(sorted(SUPPORTED_IMAGE_TYPES))
            raise InvalidUploadError(f"Unsupported image type. Allowed types: {allowed}")
        if size_bytes <= 0:
            raise InvalidUploadError("Image size must be greater than zero")
        if size_bytes > self._settings.oss_max_image_size_bytes:
            max_mb = self._settings.oss_max_image_size_bytes / (1024 * 1024)
            raise InvalidUploadError(f"Image exceeds the {max_mb:g} MB limit")
        return normalized_type

    def create_upload_url(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> PresignedUpload:
        del filename  # The client filename never controls the OSS object key.
        normalized_type = self.validate_upload_request(content_type, size_bytes)
        extension = SUPPORTED_IMAGE_TYPES[normalized_type]
        now = self._now()
        object_key = f"uploads/{now:%Y/%m/%d}/{uuid4()}{extension}"
        expires = timedelta(seconds=self._settings.oss_upload_url_ttl_seconds)

        try:
            result = self._client.presign(
                oss.PutObjectRequest(
                    bucket=self._bucket,
                    key=object_key,
                    content_type=normalized_type,
                ),
                expires=expires,
            )
        except Exception as exc:
            raise OSSOperationError("Failed to create an OSS upload URL") from exc

        signed_headers = dict(result.signed_headers or {})
        signed_headers.setdefault("Content-Type", normalized_type)
        return PresignedUpload(
            object_key=object_key,
            upload_url=result.url,
            signed_headers=signed_headers,
            expires_at=self._ensure_utc(result.expiration or now + expires),
        )

    def upload_image_bytes(
        self,
        *,
        data: bytes,
        content_type: str,
    ) -> VerifiedUpload:
        """Store a trusted in-process image, such as a Studio attachment, in OSS."""
        normalized_type = self.validate_upload_request(content_type, len(data))
        if self._detect_image_type(data) != normalized_type:
            raise InvalidUploadError("Uploaded file content does not match its image type")

        extension = SUPPORTED_IMAGE_TYPES[normalized_type]
        object_key = f"uploads/{self._now():%Y/%m/%d}/{uuid4()}{extension}"
        try:
            self._client.put_object(
                oss.PutObjectRequest(
                    bucket=self._bucket,
                    key=object_key,
                    body=data,
                    content_length=len(data),
                    content_type=normalized_type,
                    forbid_overwrite=True,
                )
            )
        except Exception as exc:
            raise OSSOperationError("Failed to upload the image to OSS") from exc

        return VerifiedUpload(
            object_key=object_key,
            content_type=normalized_type,
            size_bytes=len(data),
        )

    def verify_uploaded_image(self, object_key: str) -> VerifiedUpload:
        self._validate_object_key(object_key)
        try:
            result = self._client.head_object(
                oss.HeadObjectRequest(bucket=self._bucket, key=object_key)
            )
        except Exception as exc:
            raise OSSOperationError("Unable to inspect the uploaded OSS object") from exc

        content_type = self.normalize_content_type(result.content_type or "")
        size_bytes = result.content_length or 0
        try:
            self.validate_upload_request(content_type, size_bytes)
        except InvalidUploadError:
            self._delete_invalid_upload(object_key)
            raise

        expected_extension = SUPPORTED_IMAGE_TYPES[content_type]
        if Path(object_key).suffix.lower() != expected_extension:
            self._delete_invalid_upload(object_key)
            raise InvalidUploadError("Uploaded image type does not match its object key")

        detected_type = self._detect_uploaded_image_type(object_key)
        if detected_type != content_type:
            self._delete_invalid_upload(object_key)
            raise InvalidUploadError("Uploaded file content does not match its image type")

        return VerifiedUpload(
            object_key=object_key,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    def create_model_download_url(self, object_key: str) -> PresignedDownload:
        self._validate_object_key(object_key)
        now = self._now()
        expires = timedelta(seconds=self._settings.oss_download_url_ttl_seconds)
        try:
            result = self._client.presign(
                oss.GetObjectRequest(bucket=self._bucket, key=object_key),
                expires=expires,
            )
        except Exception as exc:
            raise OSSOperationError("Failed to create an OSS download URL") from exc

        return PresignedDownload(
            object_key=object_key,
            download_url=result.url,
            expires_at=self._ensure_utc(result.expiration or now + expires),
        )

    def delete_uploaded_image(self, object_key: str) -> None:
        self._validate_object_key(object_key)
        try:
            self._client.delete_object(
                oss.DeleteObjectRequest(bucket=self._bucket, key=object_key)
            )
        except Exception as exc:
            raise OSSOperationError("Failed to delete the OSS object") from exc

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _validate_object_key(object_key: str) -> None:
        if not UPLOAD_KEY_PATTERN.fullmatch(object_key):
            raise InvalidUploadError("Invalid upload object key")

    def _delete_invalid_upload(self, object_key: str) -> None:
        try:
            self.delete_uploaded_image(object_key)
        except Exception:
            logger.exception(
                "invalid_oss_upload_cleanup_failed",
                extra={"object_key": object_key},
            )

    def _detect_uploaded_image_type(self, object_key: str) -> str | None:
        try:
            result = self._client.get_object(
                oss.GetObjectRequest(
                    bucket=self._bucket,
                    key=object_key,
                    range_header="bytes=0-15",
                )
            )
            try:
                header = result.body.read()
            finally:
                result.body.close()
        except Exception as exc:
            raise OSSOperationError("Unable to inspect the uploaded image content") from exc

        return self._detect_image_type(header)

    @staticmethod
    def _detect_image_type(header: bytes) -> str | None:
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return "image/webp"
        return None
