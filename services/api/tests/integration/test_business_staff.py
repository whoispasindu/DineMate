import hashlib
import hmac
import math
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app import models
from app.business.models import FaceTemplate, QueueReading, StaffPresence, TillOrder
from app.business.seed import DEVICE_ID, VENUE_ID
from app.core.config import Settings, get_settings
from app.core.device_auth import hash_token
from app.main import app
from app.seed import reset, seed
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login

SIM_TOKEN = "dev-simulator-token"
DEVICE = {"Authorization": f"Device {SIM_TOKEN}"}
BASE = "/api/v1/business"
KEY = Fernet.generate_key().decode()
CAMERA = {"Authorization": "Device cafe-camera-token"}


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as c:
        app.dependency_overrides[get_settings] = lambda: Settings(deployment="local", template_key=KEY)
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def owner(client: TestClient) -> dict[str, str]:
    return login(client, "owner@dinemate.test")


def add_staff(client: TestClient, headers: dict[str, str], **body: object) -> dict[str, object]:
    response = client.post(f"{BASE}/venues/{VENUE_ID}/staff", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()["staff"]


def consent(client: TestClient, headers: dict[str, str], staff_id: object) -> None:
    response = client.post(
        f"{BASE}/staff/{staff_id}/consent", headers=headers, json={"version": "notice-v1", "signed_on": "2026-11-02"}
    )
    assert response.status_code == 200, response.text


def template() -> list[float]:
    return [math.cos(i / 3) for i in range(128)]


def test_roster_is_owner_only_and_codes_are_unique(client: TestClient) -> None:
    headers = owner(client)
    add_staff(client, headers, display_name="Test Barista", method="badge", badge_code=200, till_code="TB")
    clash = client.post(
        f"{BASE}/venues/{VENUE_ID}/staff", headers=headers, json={"display_name": "Other", "badge_code": 200}
    )
    assert clash.status_code == 409
    manager = login(client, "manager@dinemate.test")
    assert client.get(f"{BASE}/venues/{VENUE_ID}/staff", headers=manager).status_code == 403
    admin = login(client, "admin@dinemate.test")
    assert client.get(f"{BASE}/venues/{VENUE_ID}/staff", headers=admin).status_code == 403


def test_face_enrolment_needs_consent_and_a_local_server(client: TestClient, seeded: Engine) -> None:
    headers = owner(client)
    member = add_staff(client, headers, display_name="Face Worker", method="face")
    assert (
        client.post(f"{BASE}/staff/{member['id']}/face", headers=headers, json={"template": template()}).status_code
        == 409
    )
    consent(client, headers, member["id"])
    enrolled = client.post(f"{BASE}/staff/{member['id']}/face", headers=headers, json={"template": template()})
    assert enrolled.status_code == 200, enrolled.text
    assert enrolled.json()["staff"]["has_template"] is True
    with Session(seeded) as session:
        sealed = session.scalar(select(FaceTemplate.sealed))
        assert sealed is not None and b"0.9" not in sealed
    with Session(seeded) as session:
        session.add(
            models.Device(id="cam-cafe", canteen_id=VENUE_ID, kind="camera", token_hash=hash_token("cafe-camera-token"))
        )
        session.commit()
    templates = client.get("/api/v1/devices/cam-cafe/staff-templates", headers=CAMERA).json()
    faces = [s for s in templates["staff"] if s["staff_id"] == member["id"]]
    assert faces and len(faces[0]["template"]) == 128
    app.dependency_overrides[get_settings] = lambda: Settings(deployment="cloud", template_key=KEY)
    refused = client.post(f"{BASE}/staff/{member['id']}/face", headers=headers, json={"template": template()})
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "templates_disabled"
    cloud = client.get("/api/v1/devices/cam-cafe/staff-templates", headers=CAMERA).json()
    assert cloud["faces_enabled"] is False
    assert all(s["method"] == "badge" for s in cloud["staff"])


def test_campus_devices_have_no_staff_endpoints(client: TestClient) -> None:
    assert client.get("/api/v1/devices/sim-a/staff-templates", headers=DEVICE).status_code == 404


def test_presence_till_and_report_with_audit(client: TestClient, seeded: Engine) -> None:
    headers = owner(client)
    member = add_staff(client, headers, display_name="Report Barista", method="badge", badge_code=201, till_code="RB")
    stranger = {
        "staff_id": "00000000-0000-0000-0000-000000000000",
        "area": "counter",
        "started_at": datetime.now(UTC).isoformat(),
    }
    real = datetime.now(UTC)
    payload = {
        "captured_at": real.isoformat(),
        "presence": [
            {"staff_id": member["id"], "area": "counter", "started_at": (real - timedelta(minutes=30)).isoformat()}
        ],
        "queue": {"people": 3},
    }
    assert client.post(f"/api/v1/devices/{DEVICE_ID}/staff", headers=DEVICE, json=payload).status_code == 422
    consent(client, headers, member["id"])
    bad = {**payload, "presence": [stranger]}
    assert client.post(f"/api/v1/devices/{DEVICE_ID}/staff", headers=DEVICE, json=bad).status_code == 422
    accepted = client.post(f"/api/v1/devices/{DEVICE_ID}/staff", headers=DEVICE, json=payload)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["presence"] == 1
    csv = (
        "order_id,time,cashier,item,qty,unit_price\n"
        "T1,2026-11-20 12:00,RB,Latte,2,650\n"
        "T2,2026-11-20 12:10,ZZ,Tea,1,300\n"
    )
    dry = client.post(
        f"{BASE}/venues/{VENUE_ID}/till/import", headers=headers, json={"csv": csv, "dry_run": True}
    ).json()
    assert dry["saved"] is False and dry["new_orders"] == 2 and dry["unmatched_cashiers"] == ["ZZ"]
    saved = client.post(f"{BASE}/venues/{VENUE_ID}/till/import", headers=headers, json={"csv": csv}).json()
    assert saved["saved"] is True and saved["matched_cashiers"] == ["RB"]
    again = client.post(f"{BASE}/venues/{VENUE_ID}/till/import", headers=headers, json={"csv": csv}).json()
    assert again["new_orders"] == 0 and again["duplicates"] == 2
    sales = client.get(f"{BASE}/venues/{VENUE_ID}/sales?day=2026-11-20", headers=headers).json()
    rb = next(c for c in sales["by_cashier"] if c["cashier"] == "RB")
    assert rb["staff_name"] == "Report Barista" and rb["total_items"] == 2
    report = client.get(f"{BASE}/venues/{VENUE_ID}/staff-report?day=2026-11-20", headers=headers)
    assert report.status_code == 200, report.text
    worker = next(w for w in report.json()["workers"] if w["staff_id"] == member["id"])
    assert 29 <= worker["minutes"]["counter"] <= 31
    assert worker["items"] == [{"name": "Latte", "qty": 2}]
    assert report.json()["coverage"]["covered_min"] >= 29
    floor = client.get(f"{BASE}/venues/{VENUE_ID}/floor", headers=headers).json()
    assert floor["totals"]["counter_staff"] >= 1
    manager = login(client, "manager@dinemate.test")
    assert client.get(f"{BASE}/venues/{VENUE_ID}/staff-report", headers=manager).status_code == 403
    assert client.get(f"{BASE}/venues/{VENUE_ID}/sales", headers=manager).status_code == 200
    audit = client.get(f"{BASE}/audit", headers=headers).json()["items"]
    assert audit and audit[0]["action"] == "business.staff_report.view"
    client.delete(f"{BASE}/staff/{member['id']}/consent", headers=headers)
    with Session(seeded) as session:
        mine = select(func.count()).select_from(StaffPresence).where(StaffPresence.staff_id == uuid.UUID(member["id"]))
        assert session.scalar(mine) == 0
    assert client.delete(f"{BASE}/staff/{member['id']}", headers=headers).status_code == 200
    with Session(seeded) as session:
        order = session.scalars(select(TillOrder).where(TillOrder.order_ref == "T1")).one()
        assert order.staff_id is None and order.cashier_code == "RB"


def test_live_link_is_signed_with_the_device_token(client: TestClient, seeded: Engine) -> None:
    headers = owner(client)
    added = client.post(f"{BASE}/venues/{VENUE_ID}/cameras", headers=headers, json={"label": "Till", "source": "0"})
    camera = added.json()["camera"]["id"]
    with Session(seeded) as session:
        device = session.get(models.Device, camera)
        assert device is not None
        device.token_hash = hash_token("cafe-camera-token")
        session.commit()
    url = f"{BASE}/venues/{VENUE_ID}/cameras/{camera}/live"
    assert client.get(url, headers=headers).status_code == 409
    beat = {"status": "ok", "stream_url": "http://192.168.1.20:8090/live"}
    assert client.post(f"/api/v1/devices/{camera}/heartbeat", headers=CAMERA, json=beat).status_code == 200
    away = {"status": "ok", "stream_url": "http://evil.example/live"}
    assert client.post(f"/api/v1/devices/{camera}/heartbeat", headers=CAMERA, json=away).status_code == 422
    link = client.get(url, headers=headers).json()
    parsed = urlparse(link["url"])
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    expected = hmac.new(
        hash_token("cafe-camera-token").encode(), f"{camera}:{query['exp']}".encode(), hashlib.sha256
    ).hexdigest()
    assert parsed.netloc == "192.168.1.20:8090"
    assert query["sig"] == expected


def test_work_areas_only_in_business_layouts(client: TestClient) -> None:
    admin = login(client, "admin@dinemate.test")
    layout = client.get("/api/v1/devices/sim-a/layout", headers=admin).json()
    polygons = [
        *layout["polygons"],
        {"type": "work", "area": "counter", "points": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]},
    ]
    response = client.put(
        "/api/v1/devices/sim-a/layout", headers=admin, json={"base_version": layout["version"], "polygons": polygons}
    )
    assert response.status_code == 422


def test_people_at_the_counter_count_without_enrolment(client: TestClient, seeded: Engine) -> None:
    headers = owner(client)
    captured = datetime.now(UTC).isoformat()
    body = {"captured_at": captured, "counter": {"people": 3}}
    sent = client.post(f"/api/v1/devices/{DEVICE_ID}/staff", headers=DEVICE, json=body)
    assert sent.status_code == 200, sent.text
    floor = client.get(f"{BASE}/venues/{VENUE_ID}/floor", headers=headers).json()
    assert floor["totals"]["counter_staff"] >= 3
    both = {"captured_at": captured, "queue": {"people": 4}, "counter": {"people": 0}}
    assert client.post(f"/api/v1/devices/{DEVICE_ID}/staff", headers=DEVICE, json=both).status_code == 200
    with Session(seeded) as session:
        rows = session.execute(
            select(QueueReading.people, QueueReading.counter_people).where(QueueReading.counter_people.is_not(None))
        ).all()
    assert sorted(rows, key=str) == sorted([(None, 3), (4, 0)], key=str)
    report = client.get(f"{BASE}/venues/{VENUE_ID}/staff-report", headers=headers)
    assert report.status_code == 200, report.text
    too_many = {"captured_at": captured, "counter": {"people": 101}}
    assert client.post(f"/api/v1/devices/{DEVICE_ID}/staff", headers=DEVICE, json=too_many).status_code == 422
