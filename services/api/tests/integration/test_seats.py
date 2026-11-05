import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

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


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def centre(points: list[list[float]]) -> tuple[float, float]:
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def seated_layout(client: TestClient, headers: dict[str, str], seats: int = 3) -> tuple[str, dict[str, Any]]:
    layout = client.get("/api/v1/devices/sim-b/layout", headers=headers).json()
    polygons = layout["polygons"]
    seating = next(p for p in polygons if p["type"] == "seating")
    cx, cy = centre(seating["points"])
    seating["seats"] = [
        {"seat_id": f"g{i}", "x": round(cx + (i - 1) * 0.01, 4), "y": round(cy, 4)} for i in range(seats)
    ]
    saved = client.put(
        "/api/v1/devices/sim-b/layout", headers=headers, json={"base_version": layout["version"], "polygons": polygons}
    )
    assert saved.status_code == 200, saved.text
    return seating["zone_id"], saved.json()


def snapshot(zone_id: str, seats: list[dict[str, Any]], **zone: Any) -> dict[str, Any]:
    counts = {"free": 0, "occupied": 0, "held": 0, "unknown": 0}
    for seat in seats:
        counts[seat["state"]] += 1
    return {
        "captured_at": (datetime.now(UTC) - timedelta(seconds=2)).isoformat(),
        "zones": [{"zone_id": zone_id, **counts, **zone}],
        "seats": [{"zone_id": zone_id, **seat} for seat in seats],
    }


def test_layout_seats_set_capacity_and_reach_the_worker(client: TestClient, seeded: Engine) -> None:
    admin = login(client, ADMIN)
    zone_id, layout = seated_layout(client, admin)
    seating = next(p for p in layout["polygons"] if p.get("zone_id") == zone_id)
    assert [s["seat_id"] for s in seating["seats"]] == ["g0", "g1", "g2"]
    zone = next(z for z in layout["zones"] if z["id"] == zone_id)
    assert zone["capacity"] == 3
    config = client.get("/api/v1/devices/sim-b/config", headers=SIM_TOKEN).json()
    seated = next(z for z in config["zones"] if z["zone_id"] == zone_id)
    assert [s["seat_id"] for s in seated["seats"]] == ["g0", "g1", "g2"]
    assert config["settings"]["clear_s"] == 30
    assert config["settings"]["seat_radius"] == 0.06
    with Session(seeded) as session:
        entry = session.scalars(
            select(models.AuditLog).where(models.AuditLog.action == "layout.save").order_by(models.AuditLog.id.desc())
        ).first()
        assert entry is not None
        assert entry.after["seats"] == 3
        assert entry.after["capacity_from_seats"] == {zone_id: 3}


def test_layout_rejects_misplaced_and_duplicate_seats(client: TestClient) -> None:
    admin = login(client, ADMIN)
    layout = client.get("/api/v1/devices/sim-b/layout", headers=admin).json()
    polygons = layout["polygons"]
    seating = next(p for p in polygons if p["type"] == "seating")
    cx, cy = centre(seating["points"])

    def put(seats: list[dict[str, Any]]) -> dict[str, Any]:
        seating["seats"] = seats
        body = {"base_version": layout["version"], "polygons": polygons}
        return client.put("/api/v1/devices/sim-b/layout", headers=admin, json=body).json()

    outside = put([{"seat_id": "x", "x": 0.0, "y": 0.0}])
    assert outside["error"]["message"] == "Seats must be inside their seating polygon."
    twice = put([{"seat_id": "x", "x": cx, "y": cy}, {"seat_id": "x", "x": cx, "y": cy}])
    assert twice["error"]["message"] == "Each seat needs its own id."


def test_snapshots_track_states_sessions_and_summaries(client: TestClient, seeded: Engine) -> None:
    admin = login(client, ADMIN)
    zone_id, _ = seated_layout(client, admin)
    first = [
        {"seat_id": "g0", "state": "occupied", "for_s": 300},
        {"seat_id": "g1", "state": "free", "for_s": 60},
        {"seat_id": "g2", "state": "held", "for_s": 120},
    ]
    response = client.post("/api/v1/devices/sim-b/seats", headers=SIM_TOKEN, json=snapshot(zone_id, first))
    assert response.status_code == 200, response.text
    assert response.json()["changed"] == 3
    second = [
        {"seat_id": "g0", "state": "occupied", "for_s": 330, "free_soon": True},
        {"seat_id": "g1", "state": "occupied", "for_s": 5},
        {"seat_id": "g2", "state": "held", "for_s": 150},
    ]
    response = client.post(
        "/api/v1/devices/sim-b/seats", headers=SIM_TOKEN, json=snapshot(zone_id, second, free_soon=1, standing=2)
    )
    assert response.json()["changed"] == 1
    with Session(seeded) as session:
        sessions = session.scalars(
            select(models.SeatSession).where(models.SeatSession.seat_id == "g1").order_by(models.SeatSession.id)
        ).all()
        assert [(s.state, s.ended_at is None) for s in sessions] == [("free", False), ("occupied", True)]
        assert all(s.is_simulated for s in sessions)

    canteen = client.get("/api/v1/canteens/b/seats").json()
    zone = canteen["zones"][0]
    assert (zone["freshness"], zone["seats"], zone["occupied"], zone["held"], zone["free"]) == ("live", 3, 2, 1, 0)
    assert (zone["free_soon"], zone["standing"], canteen["held"]) == (1, 2, 1)
    overview = {i["canteen_id"]: i for i in client.get("/api/v1/seats/overview").json()["items"]}
    assert overview["b"]["held"] == 1

    seat_map = client.get(f"/api/v1/zones/{zone_id}/seats", headers=admin).json()
    assert [(s["seat_id"], s["state"], s["free_soon"]) for s in seat_map["seats"]] == [
        ("g0", "occupied", True),
        ("g1", "occupied", False),
        ("g2", "held", False),
    ]
    other_manager = login(client, MANAGER_A)
    assert client.get(f"/api/v1/zones/{zone_id}/seats", headers=other_manager).status_code == 403


def test_snapshot_rejects_unknown_zones_and_seats(client: TestClient) -> None:
    admin = login(client, ADMIN)
    zone_id, _ = seated_layout(client, admin)
    stray = client.post(
        "/api/v1/devices/sim-b/seats",
        headers=SIM_TOKEN,
        json=snapshot(zone_id, [{"seat_id": "nope", "state": "free", "for_s": 1}]),
    )
    assert stray.status_code == 422
    assert stray.json()["error"]["details"]["seat_ids"] == ["nope"]
    other = snapshot("00000000-0000-0000-0000-000000000000", [])
    assert client.post("/api/v1/devices/sim-b/seats", headers=SIM_TOKEN, json=other).status_code == 422


def test_old_seat_data_shows_no_numbers(client: TestClient, seeded: Engine) -> None:
    admin = login(client, ADMIN)
    zone_id, _ = seated_layout(client, admin)
    seats = [{"seat_id": "g0", "state": "held", "for_s": 10}]
    client.post("/api/v1/devices/sim-b/seats", headers=SIM_TOKEN, json=snapshot(zone_id, seats))
    with client_at(seeded, LUNCH_NOW + timedelta(minutes=11)) as later:
        zone = later.get("/api/v1/canteens/b/seats").json()["zones"][0]
        assert zone["freshness"] == "unavailable"
        assert zone["held"] is None and zone["free"] is None
        seat_map = later.get(f"/api/v1/zones/{zone_id}/seats", headers=login(later, ADMIN)).json()
        assert {s["state"] for s in seat_map["seats"]} == {"unknown"}


def test_stay_times_learn_from_finished_seat_sessions(client: TestClient, seeded: Engine) -> None:
    admin = login(client, ADMIN)
    zone_id, _ = seated_layout(client, admin)
    with Session(seeded) as session:
        zone = uuid.UUID(zone_id)
        for minutes in (15, 20, 25, 40):
            started = LUNCH_NOW - timedelta(hours=2)
            session.add(
                models.SeatSession(
                    zone_id=zone,
                    seat_id="g0",
                    state="occupied",
                    started_at=started,
                    ended_at=started + timedelta(minutes=minutes),
                )
            )
        for seat in ("g1", "g2"):
            session.add(
                models.SeatSession(
                    zone_id=zone, seat_id=seat, state="occupied", started_at=LUNCH_NOW - timedelta(minutes=18)
                )
            )
        session.commit()
    stays = client.get("/api/v1/canteens/b/stay-times", headers=admin).json()
    assert (stays["sessions"], stays["median_minutes"], stays["occupied_now"]) == (4, 22.5, 2)
    assert stays["likely_free_10min"] == 1
    assert stays["is_experimental"] is True
    assert stays["hours"][0]["sessions"] == 4
    assert client.get("/api/v1/canteens/b/stay-times", headers=login(client, MANAGER_A)).status_code == 403
