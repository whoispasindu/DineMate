from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.business.models import TableVisit, VenueTable
from app.business.seed import DEVICE_ID, VENUE_ID
from app.business.service import purge_expired
from app.main import app
from app.seed import reset, seed
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login

SIM_TOKEN = {"Authorization": "Device dev-simulator-token"}
OWNER = "owner@dinemate.test"
MANAGER = "manager@dinemate.test"
ADMIN = "admin@dinemate.test"
BASE = "/api/v1/business"


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def floor(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get(f"{BASE}/venues/{VENUE_ID}/floor", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def table_named(data: dict[str, Any], name: str) -> dict[str, Any]:
    return next(t for t in data["tables"] if t["name"] == name)


def snapshot(client: TestClient, layout: dict[str, Any], states: dict[str, dict[str, Any]]) -> None:
    seats = []
    counts: dict[str, dict[str, int]] = {}
    for zone in layout["zones"]:
        zone_counts = counts.setdefault(zone["zone_id"], {"free": 0, "occupied": 0, "held": 0, "unknown": 0})
        for seat in zone["seats"]:
            info = states.get(seat["seat_id"], {"state": "free"})
            zone_counts[info["state"]] += 1
            seats.append(
                {
                    "seat_id": seat["seat_id"],
                    "zone_id": zone["zone_id"],
                    "state": info["state"],
                    "for_s": info.get("for_s", 600),
                    "free_soon": info.get("free_soon", False),
                }
            )
    payload = {
        "captured_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "zones": [{"zone_id": z, **c} for z, c in counts.items()],
        "seats": seats,
    }
    response = client.post(f"/api/v1/devices/{DEVICE_ID}/seats", headers=SIM_TOKEN, json=payload)
    assert response.status_code == 200, response.text


def layout_of(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get(f"{BASE}/venues/{VENUE_ID}/tables", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_owner_sees_the_sample_cafe_with_tables_and_history(client: TestClient) -> None:
    headers = login(client, OWNER)
    venues = client.get(f"{BASE}/venues", headers=headers).json()["items"]
    assert [v["id"] for v in venues] == [VENUE_ID]
    assert venues[0]["is_sample"] and venues[0]["tables"] == 12
    data = floor(client, headers)
    assert data["totals"]["tables"] == 12
    assert {t["state"] for t in data["tables"]} <= {"free", "occupied", "held", "needs_clearing", "unknown"}
    customers = client.get(f"{BASE}/venues/{VENUE_ID}/customers", headers=headers).json()
    assert customers["is_sample"]
    assert len(customers["by_hour"]) == 24
    report = client.get(f"{BASE}/venues/{VENUE_ID}/reports?range=week", headers=headers).json()
    assert len(report["days"]) == 7
    assert sum(cell["visits"] for cell in report["heat"]) > 100


def test_campus_and_business_are_kept_apart(client: TestClient) -> None:
    admin = login(client, ADMIN)
    assert client.get(f"{BASE}/venues", headers=admin).status_code == 403
    owner = login(client, OWNER)
    assert client.get("/api/v1/console/overview", headers=owner).status_code == 403
    summary = client.get("/api/v1/student/summary").json()
    assert VENUE_ID not in {c["id"] for c in summary["canteens"]}
    assert client.get(f"/api/v1/canteens/{VENUE_ID}").status_code == 404
    assert client.get(f"/api/v1/canteens/{VENUE_ID}/seats").status_code == 404
    overview = client.get("/api/v1/seats/overview").json()
    assert VENUE_ID not in {i["canteen_id"] for i in overview["items"]}
    devices = client.get("/api/v1/manage/devices", headers=admin).json()["items"]
    assert DEVICE_ID not in {d["id"] for d in devices}


def test_seat_snapshots_drive_table_states_and_visits(client: TestClient, seeded: Engine) -> None:
    headers = login(client, MANAGER)
    layout = layout_of(client, headers)
    snapshot(client, layout, {})
    assert table_named(floor(client, headers), "T4")["state"] == "free"
    snapshot(client, layout, {"T4-1": {"state": "occupied", "for_s": 300}, "T4-2": {"state": "occupied", "for_s": 280}})
    t4 = table_named(floor(client, headers), "T4")
    assert t4["state"] == "occupied"
    assert t4["party_size"] == 2
    assert t4["seated_min"] == 5
    assert t4["estimate"] is not None
    with Session(seeded) as session:
        table_id = session.scalars(select(VenueTable.id).where(VenueTable.name == "T4")).one()
        open_visit = session.scalars(
            select(TableVisit).where(TableVisit.table_id == table_id, TableVisit.ended_at.is_(None))
        ).one()
        assert open_visit.party_size == 2
        open_visit.last_seen_at = open_visit.last_seen_at - timedelta(minutes=5)
        session.commit()
    snapshot(client, layout, {"T4-1": {"state": "free", "free_soon": True}})
    t4 = table_named(floor(client, headers), "T4")
    assert t4["state"] == "needs_clearing"
    with Session(seeded) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(TableVisit)
                .where(TableVisit.table_id == table_id, TableVisit.ended_at.is_(None))
            )
            == 0
        )
    cleared = client.post(f"{BASE}/tables/{t4['id']}/cleared", headers=headers)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["state"] == "free"


def test_tables_editor_validates_and_saves(client: TestClient) -> None:
    headers = login(client, OWNER)
    layout = layout_of(client, headers)
    tables = layout["tables"]
    clash = [dict(tables[0]), {**tables[1], "seat_ids": tables[0]["seat_ids"][:1]}]
    response = client.put(f"{BASE}/venues/{VENUE_ID}/tables", headers=headers, json={"tables": clash})
    assert response.status_code == 422
    stray = [{**tables[0], "seat_ids": ["nope"]}]
    assert client.put(f"{BASE}/venues/{VENUE_ID}/tables", headers=headers, json={"tables": stray}).status_code == 422
    renamed = [{**t, "name": "W1"} if t["name"] == "T1" else t for t in tables]
    saved = client.put(f"{BASE}/venues/{VENUE_ID}/tables", headers=headers, json={"tables": renamed})
    assert saved.status_code == 200, saved.text
    names = [t["name"] for t in saved.json()["tables"]]
    assert "W1" in names and "T1" not in names and len(names) == 12


def test_only_the_owner_changes_retention(client: TestClient) -> None:
    manager = login(client, MANAGER)
    assert client.patch(f"{BASE}/settings", headers=manager, json={"retention_days": 30}).status_code == 403
    owner = login(client, OWNER)
    response = client.patch(f"{BASE}/settings", headers=owner, json={"retention_days": 30})
    assert response.status_code == 200
    assert response.json()["retention_days"] == 30
    assert client.patch(f"{BASE}/settings", headers=owner, json={"retention_days": 3}).status_code == 422


def test_purge_removes_visits_past_retention(client: TestClient, seeded: Engine) -> None:
    with Session(seeded) as session:
        before = session.scalar(select(func.count()).select_from(TableVisit))
        removed = purge_expired(session, LUNCH_NOW + timedelta(days=80))
        session.commit()
        after = session.scalar(select(func.count()).select_from(TableVisit))
    assert removed > 0
    assert before is not None and after is not None and after == before - removed
