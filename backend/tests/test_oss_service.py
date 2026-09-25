from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from backend.app.core.config import Settings
from backend.app.services.oss_service import InvalidUploadError, OSSService

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


class FakeOSSClient:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []
        self.head_content_type = "image/jpeg"
        self.head_content_length = 1024
        self.object_header = b"\xff\xd8\xff\xe0fake-jpeg"
        self.presign_requests: list[object] = []
        self.put_requests: list[object] = []

    def presign(self, request: object, **_: object) -> SimpleNamespace:
        self.presign_requests.append(request)
        method = "PUT" if request.__class__.__name__ == "PutObjectRequest" else "GET"
        return SimpleNamespace(
            method=method,
            url=f"https://example.invalid/{request.key}",
            expiration=NOW + timedelta(minutes=15),
            signed_headers={"Content-Type": "image/jpeg"} if method == "PUT" else {},
        )

    def head_object(self, _: object) -> SimpleNamespace:
        return SimpleNamespace(
            content_type=self.head_content_type,
            content_length=self.head_content_length,
        )

    def get_object(self, _: object) -> SimpleNamespace:
        body = SimpleNamespace(
            read=lambda: self.object_header,
            close=lambda: None,
        )
        return SimpleNamespace(body=body)

    def delete_object(self, request: object) -> SimpleNamespace:
        self.deleted_keys.append(request.key)
        return SimpleNamespace()

    def put_object(self, request: object) -> SimpleNamespace:
        self.put_requests.append(request)
        return SimpleNamespace()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        oss_region="cn-shanghai",
        oss_endpoint="https://oss-cn-shanghai.aliyuncs.com",
        oss_bucket="test-bucket",
        oss_access_key_id=SecretStr("test-id"),
        oss_access_key_secret=SecretStr("test-secret"),
        oss_max_image_size_bytes=5 * 1024 * 1024,
    )


@pytest.fixture
def fake_client() -> FakeOSSClient:
    return FakeOSSClient()


@pytest.fixture
def service(settings: Settings, fake_client: FakeOSSClient) -> OSSService:
    return OSSService(settings, client=fake_client, now=lambda: NOW)


def test_create_upload_url_uses_server_generated_key(service: OSSService) -> None:
    ticket = service.create_upload_url(
        filename="../../unsafe name.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
    )

    assert ticket.object_key.startswith("uploads/2026/09/23/")
    assert ticket.object_key.endswith(".jpg")
    assert "unsafe name" not in ticket.object_key
    assert ticket.signed_headers["Content-Type"] == "image/jpeg"


@pytest.mark.parametrize("content_type", ["image/gif", "text/plain", "application/pdf"])
def test_create_upload_url_rejects_unsupported_type(
    service: OSSService, content_type: str
) -> None:
    with pytest.raises(InvalidUploadError, match="Unsupported image type"):
        service.create_upload_url(
            filename="file.bin",
            content_type=content_type,
            size_bytes=1024,
        )


def test_create_upload_url_rejects_large_image(service: OSSService) -> None:
    with pytest.raises(InvalidUploadError, match="5 MB limit"):
        service.create_upload_url(
            filename="large.png",
            content_type="image/png",
            size_bytes=6 * 1024 * 1024,
        )


def test_upload_image_bytes_stores_valid_image_in_oss(
    service: OSSService,
    fake_client: FakeOSSClient,
) -> None:
    data = b"\x89PNG\r\n\x1a\n" + b"image-data"

    result = service.upload_image_bytes(data=data, content_type="image/png")

    assert result.object_key.startswith("uploads/2026/09/23/")
    assert result.object_key.endswith(".png")
    assert result.size_bytes == len(data)
    request = fake_client.put_requests[0]
    assert request.body == data
    assert request.content_type == "image/png"


def test_upload_image_bytes_rejects_spoofed_content_type(service: OSSService) -> None:
    with pytest.raises(InvalidUploadError, match="content does not match"):
        service.upload_image_bytes(
            data=b"not-a-real-png",
            content_type="image/png",
        )


def test_verify_uploaded_image(service: OSSService) -> None:
    object_key = "uploads/2026/09/23/12345678-1234-1234-1234-123456789abc.jpg"

    result = service.verify_uploaded_image(object_key)

    assert result.object_key == object_key
    assert result.content_type == "image/jpeg"
    assert result.size_bytes == 1024


def test_verify_rejects_untrusted_object_key(service: OSSService) -> None:
    with pytest.raises(InvalidUploadError, match="Invalid upload object key"):
        service.verify_uploaded_image("private/another-users-image.jpg")


def test_verify_deletes_invalid_uploaded_object(
    service: OSSService, fake_client: FakeOSSClient
) -> None:
    object_key = "uploads/2026/09/23/12345678-1234-1234-1234-123456789abc.jpg"
    fake_client.head_content_type = "text/plain"

    with pytest.raises(InvalidUploadError, match="Unsupported image type"):
        service.verify_uploaded_image(object_key)

    assert fake_client.deleted_keys == [object_key]


def test_verify_rejects_spoofed_content_type(
    service: OSSService, fake_client: FakeOSSClient
) -> None:
    object_key = "uploads/2026/09/23/12345678-1234-1234-1234-123456789abc.jpg"
    fake_client.object_header = b"this is not an image"

    with pytest.raises(InvalidUploadError, match="content does not match"):
        service.verify_uploaded_image(object_key)

    assert fake_client.deleted_keys == [object_key]


def test_create_model_download_url(service: OSSService) -> None:
    object_key = "uploads/2026/09/23/12345678-1234-1234-1234-123456789abc.jpg"

    ticket = service.create_model_download_url(object_key)

    assert ticket.object_key == object_key
    assert ticket.download_url.endswith(object_key)
    assert ticket.expires_at.tzinfo is UTC


def test_delete_uploaded_image(service: OSSService, fake_client: FakeOSSClient) -> None:
    object_key = "uploads/2026/09/23/12345678-1234-1234-1234-123456789abc.jpg"

    service.delete_uploaded_image(object_key)

    assert fake_client.deleted_keys == [object_key]
