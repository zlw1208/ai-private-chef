from fastapi.testclient import TestClient

from backend.app.main import app


def test_api_info_returns_service_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/api/info")

    assert response.status_code == 200
    assert response.json() == {
        "name": "AI Private Chef",
        "version": "0.1.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }


def test_root_serves_frontend() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI 私厨" in response.text


def test_frontend_assets_are_served() -> None:
    with TestClient(app) as client:
        response = client.get("/assets/chat.js")

    assert response.status_code == 200
    assert "streamChat" in response.text


def test_health_returns_ok_and_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    payload = response.json()
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert payload["status"] == "ok"
    assert payload["service"] == "AI Private Chef"
    assert payload["environment"] == "development"
    assert payload["version"] == "0.1.0"
    assert payload["timestamp"].endswith("Z")
