from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app import models
from app.forecast_report import build_report
from app.main import app
from app.seed import reset, seed
from app.seed_history import generate
from app.services.history import clear_cache
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    clear_cache()
    with client_at(seeded, LUNCH_NOW) as c:
        yield c
    app.dependency_overrides.clear()
    clear_cache()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def test_recommendation_follows_plan_rules(client: TestClient) -> None:
    from_a = client.get("/api/v1/recommendations?from_canteen=a").json()
    assert from_a["recommendation"] | {"available_range": None} == {
        "canteen_id": "b",
        "name": "Canteen B",
        "level": "normal",
        "free_about": 32,
        "available_range": None,
        "walk_minutes": 4,
        "reason": "Lower crowding with live data",
    }
    assert from_a["excluded"] == [{"canteen_id": "c", "name": "Canteen C", "reason": "too_crowded"}]
    from_b = client.get("/api/v1/recommendations?from_canteen=b").json()
    assert from_b["recommendation"]["canteen_id"] == "a"
    anywhere = client.get("/api/v1/recommendations").json()
    assert (
        anywhere["recommendation"]["canteen_id"] == client.get("/api/v1/student/summary").json()["best"]["canteen_id"]
    )
    assert client.get("/api/v1/recommendations?from_canteen=zz").status_code == 404


def test_no_reliable_alternative(client: TestClient, seeded: Engine) -> None:
    with Session(seeded) as s:
        for reading in s.scalars(select(models.OccupancyReading)):
            reading.estimated_occupied = reading.occupied_low = reading.occupied_high = reading.capacity_snapshot
        s.commit()
    result = client.get("/api/v1/recommendations?from_canteen=a").json()
    assert result["recommendation"] is None and result["message"] == "No reliable alternative right now."


def test_zone_history(client: TestClient, seeded: Engine) -> None:
    with Session(seeded) as s:
        zone = s.scalars(select(models.SeatingZone).where(models.SeatingZone.name == "Main hall")).one()
    url = f"/api/v1/zones/{zone.id}/occupancy/history"
    body = client.get(url).json()
    assert body["zone_name"] == "Main hall" and body["is_simulated"] is True
    assert body["points"] and all(p["low"] <= p["mean"] <= p["high"] for p in body["points"])
    start = (LUNCH_NOW - timedelta(days=8)).isoformat()
    assert client.get(url, params={"from": start}).status_code == 422
    assert client.get(url, params={"bucket": "2m"}).status_code == 422
    assert client.get("/api/v1/zones/not-a-zone/occupancy/history").status_code == 404


def test_forecast_without_history_is_persistence(client: TestClient) -> None:
    forecast = client.get("/api/v1/canteens/b").json()["forecast"]
    assert len(forecast) == 4
    assert all(p["low"] <= 47 <= p["high"] for p in forecast)
    assert client.get("/api/v1/canteens/c").json()["forecast"]


def test_forecast_learns_from_simulated_history(client: TestClient, seeded: Engine) -> None:
    with Session(seeded) as s:
        added = generate(s, LUNCH_NOW, 21)
        assert added > 10_000
        again = generate(s, LUNCH_NOW, 21)
        assert again == added
        report = build_report(s, LUNCH_NOW)
    assert "| 30 min |" in report and "data source: **simulated**" in report
    clear_cache()
    forecast = client.get("/api/v1/canteens/b").json()["forecast"]
    assert len(forecast) == 4 and all(0 <= p["low"] <= p["high"] <= 100 for p in forecast)
    overview = client.get("/api/v1/console/overview", headers=login(client, "admin@dinemate.test")).json()
    assert [p for p in overview["occupancy_today"]["points"] if p["is_forecast"]]
