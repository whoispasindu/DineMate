from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app import models
from app.main import app
from app.seed import reset, seed
from app.services.rules import evaluate
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login

ADMIN = "admin@dinemate.test"


@pytest.fixture
def db(seeded: Engine) -> Iterator[Engine]:
    yield seeded
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def zone(session: Session, name: str, canteen: str) -> models.SeatingZone:
    return session.scalars(
        select(models.SeatingZone).where(models.SeatingZone.name == name, models.SeatingZone.canteen_id == canteen)
    ).one()


def reading(session: Session, z: models.SeatingZone, occupied: int, at: datetime, device: str) -> None:
    session.add(
        models.OccupancyReading(
            zone_id=z.id,
            device_id=device,
            captured_at=at,
            estimated_occupied=occupied,
            occupied_low=max(0, occupied - 2),
            occupied_high=min(z.capacity, occupied + 2),
            capacity_snapshot=z.capacity,
            confidence="medium",
            is_simulated=True,
        )
    )
    session.commit()


def alerts(session: Session, alert_type: str = "crowding") -> list[models.StaffAlert]:
    session.expire_all()
    return list(session.scalars(select(models.StaffAlert).where(models.StaffAlert.type == alert_type)))


def test_crowding_alert_lifecycle(db: Engine) -> None:
    t = LUNCH_NOW
    with Session(db) as s:
        main = zone(s, "Main hall", "c")
        evaluate(s, t)
        assert alerts(s) == []
        for i in range(1, 6):
            reading(s, main, 43, t + timedelta(seconds=30 * i), "sim-c")
            evaluate(s, t + timedelta(seconds=30 * i))
        opened = [a for a in alerts(s) if a.zone_id == main.id]
        assert [(a.level, a.status) for a in opened] == [("crowded", "open")]

        with client_at(db, t + timedelta(seconds=150)) as client:
            assert client.get("/api/v1/alerts").status_code == 401
            staff = login(client, ADMIN)
            listed = client.get("/api/v1/alerts", headers=staff).json()["items"]
            alert_id = next(a["id"] for a in listed if a["title"] == "Canteen C — Main hall")
            acked = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=staff).json()
            assert (acked["status"], acked["acknowledged_by"]) == ("acknowledged", "Campus administrator")

        for i in range(6, 12):
            reading(s, main, 47, t + timedelta(seconds=30 * i), "sim-c")
            evaluate(s, t + timedelta(seconds=30 * i))
        escalated = [a for a in alerts(s) if a.zone_id == main.id]
        assert [(a.level, a.status) for a in escalated] == [("near_capacity", "open")]

        evaluate(s, t + timedelta(seconds=30 * 11 + 200))
        assert [a.status for a in alerts(s) if a.zone_id == main.id] == ["suspended"]

        later = t + timedelta(minutes=10)
        for i in range(0, 12):
            reading(s, main, 20, later + timedelta(seconds=30 * i), "sim-c")
            evaluate(s, later + timedelta(seconds=30 * i))
        final = [a for a in alerts(s) if a.zone_id == main.id]
        assert len(final) == 1
        assert final[0].status == "resolved"


def test_flapping_readings_never_duplicate_alerts(db: Engine) -> None:
    t = LUNCH_NOW
    with Session(db) as s:
        upper = zone(s, "Upper deck", "c")
        for i in range(120):
            occupied = 20 if i % 2 == 0 else 18
            reading(s, upper, occupied, t + timedelta(seconds=30 * i), "sim-c")
            evaluate(s, t + timedelta(seconds=30 * i))
        assert len([a for a in alerts(s) if a.zone_id == upper.id]) <= 1


def test_sensor_offline_and_data_stale(db: Engine) -> None:
    t = LUNCH_NOW
    with Session(db) as s:
        balcony = s.get(models.Device, "cam-a-balcony")
        assert balcony is not None
        balcony.is_enabled = True
        balcony.last_heartbeat_at = t - timedelta(minutes=5)
        sim_b = s.get(models.Device, "sim-b")
        assert sim_b is not None
        sim_b.last_heartbeat_at = t + timedelta(minutes=4)
        s.commit()
        evaluate(s, t + timedelta(minutes=4))
        assert [a.device_id for a in alerts(s, "sensor_offline")] == ["cam-a-balcony"]
        assert {str(a.zone_id) for a in alerts(s, "data_stale")} == {
            str(zone(s, "Garden side", "b").id),
            str(zone(s, "Indoor hall", "b").id),
        }
        balcony.last_heartbeat_at = t + timedelta(minutes=5)
        s.commit()
        evaluate(s, t + timedelta(minutes=5))
        assert [a.status for a in alerts(s, "sensor_offline")] == ["resolved"]


def test_notices_and_console_overview(db: Engine) -> None:
    t = LUNCH_NOW
    with Session(db) as s:
        main = zone(s, "Main hall", "c")
        for i in range(1, 6):
            reading(s, main, 43, t + timedelta(seconds=30 * i), "sim-c")
            evaluate(s, t + timedelta(seconds=30 * i))
        for name in ("Garden side", "Indoor hall"):
            reading(s, zone(s, name, "b"), 14, t + timedelta(seconds=150), "sim-b")
    now = t + timedelta(seconds=150)
    with client_at(db, now) as client:
        feed = client.get("/api/v1/notices").json()
        kinds = {n["kind"]: n for n in feed["notices"]}
        assert set(kinds) == {"crowding", "sold_out", "shop_closing", "meal_starting", "data_unavailable"}
        assert kinds["crowding"]["title"] == "Canteen C Main hall is crowded"
        assert kinds["crowding"]["context"] == "try Canteen B"
        assert "Canteen B has around" in kinds["crowding"]["body"] and "6 min walk" in kinds["crowding"]["body"]
        assert {n["title"] for n in feed["notices"] if n["kind"] == "sold_out"} >= {"Fish rice & curry sold out"}
        meals = {n["title"]: n["body"] for n in feed["notices"] if n["kind"] == "meal_starting"}
        assert meals == {
            "Lunch has started": "Served until 2:00 p.m. today.",
            "Breakfast has started": "Served until 9:30 a.m. today.",
        }
        assert feed["notices"] == sorted(feed["notices"], key=lambda n: n["at"], reverse=True)

        assert client.get("/api/v1/console/overview").status_code == 401
        overview = client.get("/api/v1/console/overview", headers=login(client, ADMIN)).json()
        assert len(overview["zones"]) == 7
        assert {d["id"] for d in overview["devices"]} == {"sim-a", "sim-b", "sim-c", "cam-a-balcony"}
        assert any(a["type"] == "crowding" for a in overview["alerts"])
        assert overview["occupancy_today"]["points"]
        main_row = next(z for z in overview["zones"] if z["name"] == "Main hall")
        assert main_row["occupied"] == 43 and main_row["occupied_range"] == [41, 45]


def test_acknowledge_errors(db: Engine) -> None:
    with client_at(db, LUNCH_NOW) as client:
        staff = login(client, ADMIN)
        assert client.post("/api/v1/alerts/not-a-uuid/acknowledge", headers=staff).status_code == 404
        missing = "00000000-0000-0000-0000-000000000000"
        assert client.post(f"/api/v1/alerts/{missing}/acknowledge", headers=staff).status_code == 404
