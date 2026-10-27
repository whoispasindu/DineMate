import argparse
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app import models
from app.core.device_auth import get_real_now, hash_token
from app.devices_cli import register
from app.main import app
from app.seed import reset, seed
from tests.integration.conftest import LUNCH_NOW, client_at

SIM_TOKEN = {"Authorization": "Device dev-simulator-token"}
REAL_NOW = datetime(2026, 10, 27, 15, 0, 0, tzinfo=UTC)


@pytest.fixture
def device_api(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as client:
        app.dependency_overrides[get_real_now] = lambda: REAL_NOW
        yield client
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW)


def zone_ids(client: TestClient, device_id: str) -> list[str]:
    return [z["zone_id"] for z in client.get(f"/api/v1/devices/{device_id}/config", headers=SIM_TOKEN).json()["zones"]]


def test_config_lists_zones_and_supports_etag(device_api: TestClient) -> None:
    response = device_api.get("/api/v1/devices/sim-b/config", headers=SIM_TOKEN)
    assert response.status_code == 200
    body = response.json()
    assert [z["name"] for z in body["zones"]] == ["Garden side", "Indoor hall"]
    assert body["layout_version"] == 1
    assert body["settings"]["dwell_s"] == 20
    assert set(body["simulation"]) == {z["zone_id"] for z in body["zones"]}
    assert len(body["zones"][0]["points"]) == 4
    etag = response.headers["ETag"]
    again = device_api.get("/api/v1/devices/sim-b/config", headers={**SIM_TOKEN, "If-None-Match": etag})
    assert again.status_code == 304


def test_device_auth_errors(device_api: TestClient, seeded: Engine) -> None:
    assert device_api.get("/api/v1/devices/sim-b/config").json()["error"]["code"] == "unauthenticated"
    wrong = device_api.get("/api/v1/devices/sim-b/config", headers={"Authorization": "Device nope"})
    assert wrong.status_code == 401
    with Session(seeded) as session:
        balcony = session.get(models.Device, "cam-a-balcony")
        assert balcony is not None
        balcony.token_hash = hash_token("balcony-token")
        session.commit()
    disabled = device_api.get("/api/v1/devices/cam-a-balcony/config", headers={"Authorization": "Device balcony-token"})
    assert disabled.status_code == 403


def test_ingest_updates_student_view_on_server_clock(device_api: TestClient, seeded: Engine) -> None:
    garden, indoor = zone_ids(device_api, "sim-b")
    payload = {
        "captured_at": (REAL_NOW - timedelta(seconds=5)).isoformat(),
        "readings": [
            {"zone_id": garden, "estimated_occupied": 30, "occupied_low": 28, "occupied_high": 31},
            {"zone_id": indoor, "estimated_occupied": 99},
        ],
    }
    response = device_api.post("/api/v1/devices/sim-b/occupancy", headers=SIM_TOKEN, json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == 2
    b = next(c for c in device_api.get("/api/v1/student/summary").json()["canteens"] if c["id"] == "b")
    assert (b["percent"], b["free_about"], b["level"]) == (97, 2, "near_capacity")
    with Session(seeded) as session:
        latest = session.scalars(
            select(models.OccupancyReading)
            .where(models.OccupancyReading.device_id == "sim-b")
            .order_by(models.OccupancyReading.id.desc())
        ).first()
        assert latest is not None
        assert latest.captured_at == LUNCH_NOW - timedelta(seconds=5)
        assert (latest.estimated_occupied, latest.occupied_high, latest.capacity_snapshot) == (28, 28, 28)
        assert latest.is_simulated is True


def test_ingest_rejects_future_and_foreign_zones(device_api: TestClient) -> None:
    garden = zone_ids(device_api, "sim-b")[0]
    future = {
        "captured_at": (REAL_NOW + timedelta(minutes=5)).isoformat(),
        "readings": [{"zone_id": garden, "estimated_occupied": 3}],
    }
    response = device_api.post("/api/v1/devices/sim-b/occupancy", headers=SIM_TOKEN, json=future)
    assert response.status_code == 422
    foreign = {"captured_at": REAL_NOW.isoformat(), "readings": [{"zone_id": garden, "estimated_occupied": 3}]}
    response = device_api.post("/api/v1/devices/sim-a/occupancy", headers=SIM_TOKEN, json=foreign)
    assert response.status_code == 422
    assert response.json()["error"]["details"] == {"zone_ids": [garden]}
    naive = {"captured_at": "2026-10-27T15:00:00", "readings": [{"zone_id": garden, "estimated_occupied": 3}]}
    assert device_api.post("/api/v1/devices/sim-b/occupancy", headers=SIM_TOKEN, json=naive).status_code == 422


def test_heartbeat_is_recorded(device_api: TestClient, seeded: Engine) -> None:
    body = {"status": "ok", "fps": 4.2, "latency_ms": 310}
    assert device_api.post("/api/v1/devices/sim-c/heartbeat", headers=SIM_TOKEN, json=body).status_code == 200
    with Session(seeded) as session:
        beat = session.scalars(select(models.DeviceHeartbeat).where(models.DeviceHeartbeat.device_id == "sim-c")).one()
        assert (beat.status, beat.fps, beat.received_at) == ("ok", 4.2, LUNCH_NOW)


def test_register_webcam_device_end_to_end(device_api: TestClient, seeded: Engine, tmp_path: Path) -> None:
    layout = tmp_path / "webcam.json"
    layout.write_text(
        json.dumps(
            {
                "zones": [
                    {"name": "Desk zone", "capacity": 4, "points": [[0.1, 0.4], [0.9, 0.4], [0.9, 0.95], [0.1, 0.95]]}
                ],
                "ignore": [{"type": "walkway", "points": [[0, 0], [1, 0], [1, 0.2]]}],
            }
        )
    )
    args = argparse.Namespace(
        id="cam-webcam",
        canteen="pilot",
        canteen_name="Pilot (webcam)",
        layout=str(layout),
        rotate=False,
        dwell_s=10.0,
        post_every_s=None,
        smoothing_s=None,
        fps=None,
    )
    with Session(seeded) as session:
        token = register(session, args)
    assert token
    headers = {"Authorization": f"Device {token}"}
    config = device_api.get("/api/v1/devices/cam-webcam/config", headers=headers).json()
    assert (config["kind"], config["canteen_id"], config["settings"]["dwell_s"]) == ("camera", "pilot", 10)
    assert config["ignore"][0]["type"] == "walkway"
    zone = config["zones"][0]["zone_id"]
    posted = device_api.post(
        "/api/v1/devices/cam-webcam/occupancy",
        headers=headers,
        json={"captured_at": REAL_NOW.isoformat(), "readings": [{"zone_id": zone, "estimated_occupied": 1}]},
    )
    assert posted.status_code == 200
    pilot = next(c for c in device_api.get("/api/v1/student/summary").json()["canteens"] if c["id"] == "pilot")
    assert (pilot["name"], pilot["free_about"], pilot["is_sample"]) == ("Pilot (webcam)", 3, False)
