from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app import models
from app.main import app
from app.seed import reset, seed
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login

SIM_TOKEN = {"Authorization": "Device dev-simulator-token"}
ADMIN = "admin@dinemate.test"
MANAGER_A = "canteen.a@dinemate.test"
RICE = "rice.stall@dinemate.test"


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def test_layout_versions_rollback_and_worker_config(client: TestClient) -> None:
    manager = login(client, MANAGER_A)
    devices = client.get("/api/v1/manage/devices", headers=manager).json()["items"]
    assert {d["id"] for d in devices} == {"sim-a", "cam-a-balcony"}
    layout = client.get("/api/v1/devices/sim-a/layout", headers=manager).json()
    assert layout["version"] == 1
    first_config = client.get("/api/v1/devices/sim-a/config", headers=SIM_TOKEN)
    etag = first_config.headers["ETag"]

    seating = next(p for p in layout["polygons"] if p["type"] == "seating")
    moved = [{**seating, "points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.6], [0.1, 0.6]]}]
    saved = client.put("/api/v1/devices/sim-a/layout", headers=manager, json={"base_version": 1, "polygons": moved})
    assert saved.status_code == 200 and saved.json()["version"] == 2
    stale = client.put("/api/v1/devices/sim-a/layout", headers=manager, json={"base_version": 1, "polygons": moved})
    assert (stale.status_code, stale.json()["error"]["details"]) == (409, {"current_version": 2})

    changed = client.get("/api/v1/devices/sim-a/config", headers={**SIM_TOKEN, "If-None-Match": etag})
    assert changed.status_code == 200 and changed.json()["layout_version"] == 2
    assert [z["points"] for z in changed.json()["zones"]] == [moved[0]["points"]]

    rolled = client.post("/api/v1/devices/sim-a/layout/rollback", headers=manager, json={"version": 1}).json()
    assert rolled["version"] == 3 and rolled["polygons"] == layout["polygons"]
    assert [h["version"] for h in rolled["history"]] == [3, 2, 1]

    foreign = client.get("/api/v1/manage/devices", headers=login(client, ADMIN)).json()["items"]
    sim_b_zone = client.get("/api/v1/devices/sim-b/layout", headers=login(client, ADMIN)).json()["zones"][0]["id"]
    assert len(foreign) == 4
    bad = [{"type": "seating", "zone_id": sim_b_zone, "points": [[0, 0], [1, 0], [1, 1]]}]
    wrong_zone = client.put("/api/v1/devices/sim-a/layout", headers=manager, json={"base_version": 3, "polygons": bad})
    assert wrong_zone.status_code == 422
    out_of_frame = [{"type": "queue", "points": [[0, 0], [1.2, 0], [1, 1]]}]
    assert (
        client.put(
            "/api/v1/devices/sim-a/layout", headers=manager, json={"base_version": 3, "polygons": out_of_frame}
        ).status_code
        == 422
    )
    denied = client.get("/api/v1/devices/sim-b/layout", headers=manager)
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "forbidden_scope")
    assert client.get("/api/v1/manage/devices", headers=login(client, RICE)).status_code == 403


def test_zone_rename_capacity_and_create(client: TestClient, seeded: Engine) -> None:
    manager = login(client, MANAGER_A)
    zone = client.get("/api/v1/devices/sim-a/layout", headers=manager).json()["zones"][0]
    renamed = client.patch(
        f"/api/v1/zones/{zone['id']}", headers=manager, json={"name": "Sample window row", "capacity": 30}
    )
    assert renamed.json()["zone"] | {"id": None} == {
        "id": None,
        "name": "Sample window row",
        "capacity": 30,
        "is_active": zone["is_active"],
        "is_monitored": zone["is_monitored"],
    }
    config = client.get("/api/v1/devices/sim-a/config", headers=SIM_TOKEN).json()
    assert any(z["name"] == "Sample window row" and z["capacity"] == 30 for z in config["zones"])
    assert client.patch(f"/api/v1/zones/{zone['id']}", headers=manager, json={"capacity": 0}).status_code == 422

    created = client.post("/api/v1/canteens/a/zones", headers=manager, json={"name": "Sample terrace", "capacity": 12})
    assert created.status_code == 201
    assert (
        client.post("/api/v1/canteens/b/zones", headers=manager, json={"name": "X", "capacity": 4}).status_code == 403
    )
    with Session(seeded) as s:
        actions = [a.action for a in s.scalars(select(models.AuditLog).where(models.AuditLog.entity == "seating_zone"))]
        assert actions == ["zone.update", "zone.create"]


def test_thresholds(client: TestClient) -> None:
    manager = login(client, MANAGER_A)
    listing = client.get("/api/v1/manage/thresholds", headers=manager).json()
    assert {z["canteen_id"] for z in listing["items"]} == {"a"}
    assert listing["defaults"]["crowded_pct"] == 80 and all(z["is_default"] for z in listing["items"])
    zone_id = listing["items"][0]["zone_id"]
    values = {
        "busy_pct": 50,
        "crowded_pct": 70,
        "near_capacity_pct": 90,
        "hysteresis_pct": 4,
        "dwell_seconds": 60,
        "alert_from": "busy",
    }
    saved = client.put(f"/api/v1/zones/{zone_id}/thresholds", headers=manager, json=values).json()["item"]
    assert saved["is_default"] is False and saved["values"] == values
    unordered = {**values, "crowded_pct": 95}
    assert client.put(f"/api/v1/zones/{zone_id}/thresholds", headers=manager, json=unordered).status_code == 422
    admin_view = client.get("/api/v1/manage/thresholds", headers=login(client, ADMIN)).json()["items"]
    other = next(z["zone_id"] for z in admin_view if z["canteen_id"] == "c")
    assert client.put(f"/api/v1/zones/{other}/thresholds", headers=manager, json=values).status_code == 403


def test_meal_schedules(client: TestClient) -> None:
    manager = login(client, MANAGER_A)
    admin = login(client, ADMIN)
    campus = client.get("/api/v1/manage/meal-schedules", headers=manager).json()
    assert campus["can_edit"] is False and campus["canteen_name"] == "Campus default"
    assert (
        client.put(
            "/api/v1/meal-schedules", headers=manager, json={"weekly": campus["weekly"], "overrides": []}
        ).status_code
        == 403
    )

    canteen = client.get("/api/v1/manage/meal-schedules?canteen_id=a", headers=manager).json()
    assert canteen["uses_campus_weekly"] is True and canteen["can_edit"] is True
    today = (LUNCH_NOW + timedelta(hours=6)).date().isoformat()
    override = {
        "canteen_id": "a",
        "weekly": None,
        "overrides": [
            {"date": today, "period": "lunch", "starts": "12:00", "ends": "13:00", "reason": "Sample exam day"}
        ],
    }
    saved = client.put("/api/v1/meal-schedules", headers=manager, json=override).json()
    assert saved["overrides"][0]["reason"] == "Sample exam day" and saved["uses_campus_weekly"] is True
    status = client.get("/api/v1/meal-status?canteen_id=a").json()
    assert status["current"]["ends"].startswith(f"{today}T07:30")

    weekly = [{"weekday": d, "period": "lunch", "starts": "11:30", "ends": "14:30"} for d in range(5)]
    own = client.put(
        "/api/v1/meal-schedules", headers=manager, json={"canteen_id": "a", "weekly": weekly, "overrides": []}
    ).json()
    assert own["uses_campus_weekly"] is False and len(own["weekly"]) == 5

    overlap = [
        {"weekday": 0, "period": "breakfast", "starts": "07:00", "ends": "12:00"},
        {"weekday": 0, "period": "lunch", "starts": "11:30", "ends": "14:00"},
    ]
    bad = [
        {"canteen_id": "a", "weekly": overlap, "overrides": []},
        {"canteen_id": "a", "weekly": None, "overrides": [{"date": today, "period": "lunch"}]},
        {"weekly": None, "overrides": []},
    ]
    assert [client.put("/api/v1/meal-schedules", headers=admin, json=b).status_code for b in bad] == [422] * 3
    assert client.get("/api/v1/manage/meal-schedules?canteen_id=b", headers=manager).status_code == 403
    assert client.get("/api/v1/manage/meal-schedules?canteen_id=zz", headers=admin).status_code == 404
    campus_edit = client.put(
        "/api/v1/meal-schedules", headers=admin, json={"weekly": campus["weekly"], "overrides": []}
    )
    assert campus_edit.status_code == 200 and campus_edit.json()["can_edit"] is True
