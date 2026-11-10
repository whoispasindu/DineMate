from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app import models
from app.business.seed import VENUE_ID
from app.core.config import Settings, get_settings
from app.core.device_auth import hash_token
from app.main import app
from app.seed import reset, seed
from app.testfeeds.hub_setup import ensure_hub
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login

HUB_TOKEN = "hub-dev-test-token"
HUB = {"Authorization": f"Device {HUB_TOKEN}"}
SIM = {"Authorization": "Device dev-simulator-token"}
CLIP = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2048
YOUTUBE = "https://youtu.be/abc"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    return tmp_path / "videos"


@pytest.fixture
def client(seeded: Engine, folder: Path) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as c:
        app.dependency_overrides[get_settings] = lambda: Settings(test_videos_dir=str(folder))
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def upload(client: TestClient, headers: dict[str, str], filename: str = "Lunch rush.MP4") -> str:
    response = client.post("/api/v1/test-videos", params={"filename": filename}, headers=headers, content=CLIP)
    assert response.status_code == 200, response.text
    return str(response.json()["source"])


def add_feed(client: TestClient, headers: dict[str, str], canteen: str, source: str = YOUTUBE) -> str:
    response = client.post(
        f"/api/v1/manage/canteens/{canteen}/test-feeds", headers=headers, json={"label": "Clip", "source": source}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["feed"]["id"])


def test_videos_upload_to_the_test_folder(client: TestClient, folder: Path) -> None:
    admin = login(client, "admin@dinemate.test")
    source = upload(client, admin)
    assert source.startswith("video:lunch-rush-")
    assert (folder / source.removeprefix("video:")).read_bytes() == CLIP
    url = "/api/v1/test-videos"
    assert client.post(url, params={"filename": "notes.txt"}, headers=admin, content=CLIP).status_code == 422
    assert client.post(url, params={"filename": "a.mp4"}, headers=admin, content=b"").status_code == 422
    assert client.post(url, params={"filename": "a.mp4"}, content=CLIP).status_code == 401
    shop = login(client, "rice.stall@dinemate.test")
    assert client.post(url, params={"filename": "a.mp4"}, headers=shop, content=CLIP).status_code == 403
    app.dependency_overrides[get_settings] = lambda: Settings(test_videos_dir=str(folder), test_video_max_mb=0)
    assert client.post(url, params={"filename": "a.mp4"}, headers=admin, content=CLIP).status_code == 413
    assert sorted(p.name for p in folder.iterdir()) == [source.removeprefix("video:")]


def test_campus_feeds_are_added_listed_and_removed(client: TestClient, folder: Path) -> None:
    manager = login(client, "canteen.a@dinemate.test")
    source = upload(client, manager)
    feed_id = add_feed(client, manager, "a", source)
    listed = client.get("/api/v1/manage/test-feeds", headers=manager).json()
    feed = listed["items"][0]
    assert [f["id"] for f in listed["items"]] == [feed_id] and listed["max_feeds"] == 8
    assert feed["status"] == "starting" and feed["source_hint"].startswith("Test video · lunch-rush-")
    devices = client.get("/api/v1/manage/devices", headers=manager).json()["items"]
    assert any(d["id"] == feed_id and d["label"] == "Clip" for d in devices)
    other = client.post("/api/v1/manage/canteens/b/test-feeds", headers=manager, json={"label": "B", "source": source})
    assert other.status_code == 403
    gone = {"label": "Gone", "source": "video:gone-abcdef.mp4"}
    assert client.post("/api/v1/manage/canteens/a/test-feeds", headers=manager, json=gone).status_code == 422
    venue = {"label": "V", "source": source}
    assert client.post(f"/api/v1/manage/canteens/{VENUE_ID}/test-feeds", headers=manager, json=venue).status_code == 404
    assert client.get(f"/api/v1/manage/test-feeds/{feed_id}/live", headers=manager).status_code == 409
    assert client.delete(f"/api/v1/manage/test-feeds/{feed_id}", headers=manager).status_code == 200
    assert not any(folder.iterdir())
    assert client.delete(f"/api/v1/manage/test-feeds/{feed_id}", headers=manager).status_code == 404
    assert client.get("/api/v1/manage/test-feeds", headers=manager).json()["items"] == []


def test_business_cameras_play_uploaded_videos(client: TestClient, folder: Path) -> None:
    owner = login(client, "owner@dinemate.test")
    source = upload(client, owner)
    added = client.post(
        f"/api/v1/business/venues/{VENUE_ID}/cameras", headers=owner, json={"label": "Clip", "source": source}
    )
    assert added.status_code == 200, added.text
    camera = added.json()["camera"]
    assert camera["source_hint"].startswith("Test video · ")
    swapped = client.patch(f"/api/v1/business/cameras/{camera['id']}", headers=owner, json={"source": YOUTUBE})
    assert swapped.status_code == 200 and not any(folder.iterdir())


def test_dev_hub_serves_campus_and_business_test_feeds(client: TestClient, seeded: Engine) -> None:
    with Session(seeded) as session:
        assert ensure_hub(session, "hub-dev", HUB_TOKEN, LUNCH_NOW) == "created"
        session.commit()
    admin = login(client, "admin@dinemate.test")
    feed = add_feed(client, admin, "b")
    owner = login(client, "owner@dinemate.test")
    camera = client.post(
        f"/api/v1/business/venues/{VENUE_ID}/cameras", headers=owner, json={"label": "Cafe", "source": "rtsp://c/1"}
    ).json()["camera"]["id"]
    listed = client.get("/api/v1/devices/hub-dev/hub/cameras", headers=HUB)
    assert listed.status_code == 200, listed.text
    assert {c["device_id"] for c in listed.json()["cameras"]} == {feed, camera}
    tokens = client.post("/api/v1/devices/hub-dev/hub/tokens", headers=HUB, json={"device_ids": [feed]})
    assert tokens.status_code == 200, tokens.text
    sim = client.post("/api/v1/devices/hub-dev/hub/tokens", headers=HUB, json={"device_ids": ["sim-a"]})
    assert sim.status_code == 404
    devices = client.get("/api/v1/manage/devices", headers=admin).json()["items"]
    assert all(d["id"] != "hub-dev" for d in devices)


def test_a_live_camera_takes_a_zone_over_from_the_simulator(client: TestClient, seeded: Engine) -> None:
    admin = login(client, "admin@dinemate.test")
    zone = client.get("/api/v1/devices/sim-a/config", headers=SIM).json()["zones"][0]["zone_id"]
    feed = add_feed(client, admin, "a")
    polygons = [{"type": "seating", "zone_id": zone, "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}]
    saved = client.put(
        f"/api/v1/devices/{feed}/layout", headers=admin, json={"base_version": None, "polygons": polygons}
    )
    assert saved.status_code == 200, saved.text
    reading = {"captured_at": datetime.now(UTC).isoformat(), "readings": [{"zone_id": zone, "estimated_occupied": 5}]}

    def accepted() -> int:
        response = client.post("/api/v1/devices/sim-a/occupancy", headers=SIM, json=reading)
        assert response.status_code == 200, response.text
        return int(response.json()["accepted"])

    def seen(ago: timedelta) -> None:
        with Session(seeded) as session:
            device = session.get(models.Device, feed)
            assert device is not None
            device.last_heartbeat_at = LUNCH_NOW - ago
            session.commit()

    assert accepted() == 1
    seen(timedelta(seconds=30))
    assert accepted() == 0
    seen(timedelta(minutes=5))
    assert accepted() == 1


def test_a_zone_drawn_on_a_camera_becomes_monitored(client: TestClient) -> None:
    admin = login(client, "admin@dinemate.test")
    created = client.post("/api/v1/canteens/a/zones", headers=admin, json={"name": "Upper hall", "capacity": 80})
    zone = created.json()["zone"]
    assert zone["is_monitored"] is False
    feed = add_feed(client, admin, "a")
    polygons = [{"type": "seating", "zone_id": zone["id"], "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}]
    body = {"base_version": None, "polygons": polygons}
    saved = client.put(f"/api/v1/devices/{feed}/layout", headers=admin, json=body)
    assert saved.status_code == 200, saved.text
    assert next(z for z in saved.json()["zones"] if z["id"] == zone["id"])["is_monitored"] is True


def test_detection_detail_is_set_per_camera(client: TestClient, seeded: Engine) -> None:
    admin = login(client, "admin@dinemate.test")
    body = {"label": "Busy hall", "source": YOUTUBE, "detail": "high"}
    feed = client.post("/api/v1/manage/canteens/a/test-feeds", headers=admin, json=body).json()["feed"]
    assert feed["detail"] == "high"
    owner = login(client, "owner@dinemate.test")
    added = client.post(
        f"/api/v1/business/venues/{VENUE_ID}/cameras", headers=owner, json={"label": "Cafe", "source": "0"}
    ).json()["camera"]
    assert added["detail"] == "auto"
    patched = client.patch(f"/api/v1/business/cameras/{added['id']}", headers=owner, json={"detail": "high"})
    assert patched.json()["camera"]["detail"] == "high"
    listed = client.get(f"/api/v1/business/venues/{VENUE_ID}/cameras", headers=owner).json()["items"]
    assert next(c for c in listed if c["id"] == added["id"])["detail"] == "high"
    with Session(seeded) as session:
        device = session.get(models.Device, added["id"])
        assert device is not None
        device.token_hash = hash_token("detail-token")
        session.commit()
    config = client.get(f"/api/v1/devices/{added['id']}/config", headers={"Authorization": "Device detail-token"})
    assert config.json()["settings"]["imgsz"] == 1280
    back = client.patch(f"/api/v1/business/cameras/{added['id']}", headers=owner, json={"detail": "auto"})
    assert back.json()["camera"]["detail"] == "auto"
    bad = client.patch(f"/api/v1/business/cameras/{added['id']}", headers=owner, json={"detail": "huge"})
    assert bad.status_code == 422
