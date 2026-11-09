import argparse
import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app import models
from app.business import setup
from app.business.seed import VENUE_ID
from app.core.config import Settings, get_settings
from app.core.device_auth import hash_token
from app.main import app
from app.seed import reset, seed
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login

BASE = "/api/v1/business"
HUB_TOKEN = "hub-test-token-123"
HUB = {"Authorization": f"Device {HUB_TOKEN}"}
SOURCE = "rtsp://admin:secret@192.168.1.50:554/stream1"


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def owner(client: TestClient) -> dict[str, str]:
    return login(client, "owner@dinemate.test")


def add_camera(client: TestClient, headers: dict[str, str], label: str = "Counter", source: str = SOURCE) -> str:
    response = client.post(
        f"{BASE}/venues/{VENUE_ID}/cameras", headers=headers, json={"label": label, "source": source}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["camera"]["id"])


def add_hub(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(models.Device(id="hub-test", canteen_id=VENUE_ID, kind="hub", token_hash=hash_token(HUB_TOKEN)))
        session.commit()


def test_cameras_are_added_masked_edited_and_removed(client: TestClient) -> None:
    headers = owner(client)
    camera = add_camera(client, headers)
    listed = client.get(f"{BASE}/venues/{VENUE_ID}/cameras", headers=headers).json()["items"]
    mine = next(c for c in listed if c["id"] == camera)
    assert mine["label"] == "Counter" and mine["source_hint"] == "rtsp://192.168.1.50:554/…"
    assert mine["status"] == "offline" and mine["has_layout"] is False
    assert "secret" not in str(listed)
    manager = login(client, "manager@dinemate.test")
    patched = client.patch(f"{BASE}/cameras/{camera}", headers=manager, json={"label": "Till", "source": "0"})
    assert patched.status_code == 200 and patched.json()["camera"]["source_hint"] == "USB camera 0"
    bad = client.post(f"{BASE}/venues/{VENUE_ID}/cameras", headers=headers, json={"label": "X", "source": "C:/a.mp4"})
    assert bad.status_code == 422
    admin = login(client, "admin@dinemate.test")
    assert client.patch(f"{BASE}/cameras/{camera}", headers=admin, json={"label": "Nope"}).status_code == 403
    assert client.delete(f"{BASE}/cameras/{camera}", headers=headers).status_code == 200
    assert client.delete(f"{BASE}/cameras/{camera}", headers=headers).status_code == 404
    after = client.get(f"{BASE}/venues/{VENUE_ID}/cameras", headers=headers).json()["items"]
    assert all(c["id"] != camera for c in after)


def test_camera_limit(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(max_cameras=1)
    headers = owner(client)
    add_camera(client, headers)
    response = client.post(f"{BASE}/venues/{VENUE_ID}/cameras", headers=headers, json={"label": "Two", "source": "1"})
    assert response.status_code == 409


def test_owner_draws_areas_and_seats_for_a_camera(client: TestClient) -> None:
    headers = owner(client)
    camera = add_camera(client, headers)
    area = client.post(f"{BASE}/venues/{VENUE_ID}/areas", headers=headers, json={"name": "Patio"})
    assert area.status_code == 200, area.text
    zone_id = area.json()["zone"]["id"]
    assert client.post(f"{BASE}/venues/{VENUE_ID}/areas", headers=headers, json={"name": "patio"}).status_code == 409
    layout = client.get(f"{BASE}/cameras/{camera}/layout", headers=headers).json()
    assert layout["version"] is None and any(z["id"] == zone_id for z in layout["zones"])
    polygons = [
        {
            "type": "seating",
            "zone_id": zone_id,
            "points": [[0.1, 0.1], [0.6, 0.1], [0.6, 0.6], [0.1, 0.6]],
            "seats": [{"seat_id": "P1", "x": 0.2, "y": 0.2}, {"seat_id": "P2", "x": 0.4, "y": 0.4}],
        },
        {"type": "work", "area": "counter", "points": [[0.7, 0.1], [0.9, 0.1], [0.9, 0.3]]},
    ]
    saved = client.put(
        f"{BASE}/cameras/{camera}/layout", headers=headers, json={"base_version": None, "polygons": polygons}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    patio = next(z for z in saved.json()["zones"] if z["id"] == zone_id)
    assert patio["capacity"] == 2
    stale = client.put(f"{BASE}/cameras/{camera}/layout", headers=headers, json={"base_version": None, "polygons": []})
    assert stale.status_code == 409
    listed = client.get(f"{BASE}/venues/{VENUE_ID}/cameras", headers=headers).json()["items"]
    assert next(c for c in listed if c["id"] == camera)["has_layout"] is True


def test_hub_lists_its_cameras_and_rotates_their_tokens(client: TestClient, seeded: Engine) -> None:
    headers = owner(client)
    camera = add_camera(client, headers)
    add_hub(seeded)
    listed = client.get("/api/v1/devices/hub-test/hub/cameras", headers=HUB)
    assert listed.status_code == 200, listed.text
    cameras = listed.json()["cameras"]
    assert [c["device_id"] for c in cameras] == [camera] and cameras[0]["source"] == SOURCE
    tokens = client.post("/api/v1/devices/hub-test/hub/tokens", headers=HUB, json={"device_ids": [camera]})
    assert tokens.status_code == 200, tokens.text
    token = tokens.json()["tokens"][0]["token"]
    config = client.get(f"/api/v1/devices/{camera}/config", headers={"Authorization": f"Device {token}"})
    assert config.status_code == 200, config.text
    again = client.post("/api/v1/devices/hub-test/hub/tokens", headers=HUB, json={"device_ids": [camera]})
    assert again.status_code == 200
    stale = client.get(f"/api/v1/devices/{camera}/config", headers={"Authorization": f"Device {token}"})
    assert stale.status_code == 401
    assert (
        client.post("/api/v1/devices/hub-test/hub/tokens", headers=HUB, json={"device_ids": ["sim-a"]}).status_code
        == 404
    )
    simulator = {"Authorization": "Device dev-simulator-token"}
    assert client.get("/api/v1/devices/sim-cafe/hub/cameras", headers=simulator).status_code == 404
    assert client.get("/api/v1/devices/hub-test/hub/cameras").status_code == 401


def test_setup_creates_a_business_once(client: TestClient, seeded: Engine) -> None:
    os.environ["SETUP_TEST_PASSWORD"] = "owner-password-123"
    os.environ["SETUP_TEST_HUB"] = HUB_TOKEN
    args = argparse.Namespace(
        org="Green Leaf Cafés",
        venue="Green Leaf Kandy",
        owner_email="owner@greenleaf.test",
        owner_name="Owner",
        password_env="SETUP_TEST_PASSWORD",
        hub_token_env="SETUP_TEST_HUB",
        opens="07:30",
        closes="20:00",
    )
    with Session(seeded) as session:
        first = setup.create(session, args)
        session.commit()
        second = setup.create(session, args)
        session.commit()
        assert any("venue v-green-leaf-kandy" in line for line in first)
        assert not any(line.startswith(("organization", "venue", "owner")) for line in second)
        venue = session.get(models.Canteen, "v-green-leaf-kandy")
        assert venue is not None and venue.kind == models.VENUE
    headers = login(client, "owner@greenleaf.test", "owner-password-123")
    venues = client.get(f"{BASE}/venues", headers=headers).json()["items"]
    assert [v["id"] for v in venues] == ["v-green-leaf-kandy"]
    assert client.get("/api/v1/devices/hub-local/hub/cameras", headers=HUB).status_code == 200
    os.environ["SETUP_TEST_PASSWORD"] = ""
    with Session(seeded) as session, pytest.raises(setup.SetupError):
        setup.create(session, argparse.Namespace(**{**vars(args), "owner_email": "x@greenleaf.test"}))
