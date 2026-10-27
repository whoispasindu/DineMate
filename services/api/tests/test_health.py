from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.db import database_reachable
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_ok_when_database_reachable(client: TestClient) -> None:
    app.dependency_overrides[database_reachable] = lambda: True
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["server_time"].endswith("Z") or "+00:00" in body["server_time"]


def test_health_degraded_when_database_down(client: TestClient) -> None:
    app.dependency_overrides[database_reachable] = lambda: False
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"


def test_openapi_is_served_under_api_prefix(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "DineMate API"


def test_cors_allows_student_app_origin(client: TestClient) -> None:
    app.dependency_overrides[database_reachable] = lambda: True
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
