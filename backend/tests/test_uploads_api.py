from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_oss_service
from backend.app.main import app
from backend.app.services.oss_service import PresignedUpload, VerifiedUpload


class StubOSSService:
    def create_upload_url(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> PresignedUpload:
        assert filename == "tomato.jpg"
        assert content_type == "image/jpeg"
        assert size_bytes == 2048
        return PresignedUpload(
            object_key="uploads/2026/09/23/example.jpg",
            upload_url="https://example.invalid/upload",
            signed_headers={"Content-Type": "image/jpeg"},
            expires_at=datetime(2026, 9, 23, 12, 15, tzinfo=UTC),
        )

    def verify_uploaded_image(self, object_key: str) -> VerifiedUpload:
        return VerifiedUpload(
            object_key=object_key,
            content_type="image/jpeg",
            size_bytes=2048,
        )


def test_create_upload_url_endpoint() -> None:
    app.dependency_overrides[get_oss_service] = StubOSSService
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/uploads/presign",
                json={
                    "filename": "tomato.jpg",
                    "content_type": "image/jpeg",
                    "size_bytes": 2048,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["method"] == "PUT"
    assert response.json()["headers"] == {"Content-Type": "image/jpeg"}


def test_complete_upload_endpoint() -> None:
    app.dependency_overrides[get_oss_service] = StubOSSService
    object_key = "uploads/2026/09/23/example.jpg"
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/uploads/complete",
                json={"object_key": object_key},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "object_key": object_key,
        "content_type": "image/jpeg",
        "size_bytes": 2048,
        "status": "verified",
    }

