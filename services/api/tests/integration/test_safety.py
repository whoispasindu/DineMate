import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.core.device_auth import hash_token
from app.main import app
from app.safety.models import SafetyEvent, SafetyInstruction, SafetySource
from app.safety.service import SIMULATION_LABEL, check_sources
from app.safety.signing import ingest_limiter, signature
from app.seed import reset, seed
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login

SIM_TOKEN = "dev-safety-sim-token"
GATEWAY_TOKEN = "approved-gateway-test-token"
OFFICER = "safety@dinemate.test"
MANAGER_A = "canteen.a@dinemate.test"


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    ingest_limiter.reset()
    with client_at(seeded, LUNCH_NOW) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def send(
    client: TestClient,
    payload: dict[str, Any],
    token: str = SIM_TOKEN,
    path: str = "/api/v1/safety/events",
    stamp: datetime | None = None,
    sign_with: str | None = None,
) -> Any:
    body = json.dumps(payload).encode()
    timestamp = (stamp or datetime.now(UTC)).isoformat()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Device {token}",
        "X-Timestamp": timestamp,
        "X-Signature": signature(sign_with or token, timestamp, body),
    }
    return client.post(path, content=body, headers=headers)


def alarm(event_id: str = "sim-000123", canteen: str = "a", claims_simulation: bool = True) -> dict[str, Any]:
    return {
        "external_event_id": event_id,
        "event_type": "fire_alarm",
        "location": {"canteen_id": canteen, "zone_id": None},
        "occurred_at": datetime.now(UTC).isoformat(),
        "is_simulation": claims_simulation,
    }


def test_simulator_is_always_labelled_on_every_surface(client: TestClient, seeded: Engine) -> None:
    accepted = send(client, alarm(claims_simulation=False))
    assert accepted.status_code == 202
    body = accepted.json()
    assert (body["is_simulation"], body["label"], body["severity"]) == (True, SIMULATION_LABEL, "critical")

    active = client.get("/api/v1/safety/active").json()
    assert active["active"] is True
    event = active["events"][0]
    assert event["is_simulation"] is True and event["title"] == "Fire alarm (simulated)"
    assert event["instructions"] == "Follow instructions from campus staff and official alarms."
    assert client.get("/api/v1/student/summary").json()["safety"]["events"][0]["id"] == body["id"]
    assert client.get("/api/v1/notices").json()["safety"]["events"][0]["is_simulation"] is True
    admin = login(client, "admin@dinemate.test")
    overview = client.get("/api/v1/console/overview", headers=admin).json()["safety"]
    assert overview["events"][0]["is_simulation"] is True
    staff = client.get("/api/v1/safety/events", headers=login(client, OFFICER)).json()["items"][0]
    assert staff["label"] == SIMULATION_LABEL and staff["source_kind"] == "simulator"
    with Session(seeded) as s:
        audit = s.scalars(select(models.AuditLog).where(models.AuditLog.action == "safety.event_received")).one()
        assert audit.after["label"] == SIMULATION_LABEL and audit.after["claimed_simulation"] is False


def test_bad_signatures_and_replays_are_rejected_and_logged(client: TestClient, seeded: Engine) -> None:
    wrong_key = send(client, alarm(), sign_with="not-the-token")
    replay = send(client, alarm(), stamp=datetime.now(UTC) - timedelta(minutes=2))
    future = send(client, alarm(), stamp=datetime.now(UTC) + timedelta(minutes=2))
    assert [r.status_code for r in (wrong_key, replay, future)] == [401, 401, 401]
    assert {r.json()["error"]["code"] for r in (wrong_key, replay, future)} == {"invalid_signature"}
    unknown = send(client, alarm(), token="who-knows")
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (401, "unauthenticated")
    tampered_body = json.dumps(alarm()).encode()
    stamp = datetime.now(UTC).isoformat()
    tampered = client.post(
        "/api/v1/safety/events",
        content=tampered_body.replace(b"fire_alarm", b"evacuation"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Device {SIM_TOKEN}",
            "X-Timestamp": stamp,
            "X-Signature": signature(SIM_TOKEN, stamp, tampered_body),
        },
    )
    assert tampered.status_code == 401
    assert client.get("/api/v1/safety/active").json()["active"] is False
    with Session(seeded) as s:
        rejected = s.scalars(select(models.AuditLog).where(models.AuditLog.action == "safety.ingest_rejected")).all()
        assert len(rejected) == 4 and all(r.actor_device_id == "safety-sim" for r in rejected)


def test_duplicate_burst_merges_into_one_event(client: TestClient, seeded: Engine) -> None:
    for i in range(50):
        if i % 10 == 0:
            ingest_limiter.reset()
        assert send(client, alarm()).status_code == 202
    ingest_limiter.reset()
    nearby = send(client, alarm(event_id="sim-other-id")).json()
    assert nearby["merged"] is True and nearby["repeat_count"] == 51
    elsewhere = send(client, alarm(event_id="sim-c", canteen="c")).json()
    assert elsewhere["merged"] is False
    with Session(seeded) as s:
        counts = sorted(e.repeat_count for e in s.scalars(select(SafetyEvent)))
        assert counts == [1, 51]


def test_ingest_rate_limit(client: TestClient) -> None:
    codes = [send(client, alarm(event_id=f"burst-{i}")).status_code for i in range(11)]
    assert codes[:10] == [202] * 10 and codes[10] == 429


def test_acknowledge_and_resolve_record_user_and_time(client: TestClient, seeded: Engine) -> None:
    event_id = send(client, alarm()).json()["id"]
    manager = login(client, MANAGER_A)
    officer = login(client, OFFICER)
    assert client.get("/api/v1/safety/events", headers=manager).status_code == 403
    assert client.post(f"/api/v1/safety/events/{event_id}/acknowledge", headers=manager, json={}).status_code == 403

    acked = client.post(
        f"/api/v1/safety/events/{event_id}/acknowledge", headers=officer, json={"note": "Seen by safety desk"}
    )
    event = acked.json()["event"]
    assert event["status"] == "acknowledged"
    assert event["acks"][0]["user_name"] == "Safety officer" and event["acks"][0]["note"] == "Seen by safety desk"
    assert client.get("/api/v1/safety/active").json()["events"][0]["status"] == "acknowledged"

    no_note = client.post(f"/api/v1/safety/events/{event_id}/resolve", headers=officer, json={"note": ""})
    assert no_note.status_code == 422
    resolved = client.post(
        f"/api/v1/safety/events/{event_id}/resolve", headers=officer, json={"note": "Drill finished"}
    ).json()
    assert resolved["event"]["resolved_by_name"] == "Safety officer" and resolved["event"]["resolved_at"] is not None
    again = client.post(f"/api/v1/safety/events/{event_id}/resolve", headers=officer, json={"note": "Again"})
    assert again.status_code == 409
    assert client.get("/api/v1/safety/active").json() | {"server_time": None} == {
        "server_time": None,
        "active": False,
        "events": [],
    }
    with Session(seeded) as s:
        rows = s.scalars(
            select(models.AuditLog).where(models.AuditLog.entity == "safety_event").order_by(models.AuditLog.id)
        ).all()
        assert [r.action for r in rows] == ["safety.event_received", "safety.acknowledge", "safety.resolve"]
        assert all(r.actor_user_id is not None for r in rows[1:]) and all(r.after["is_simulation"] for r in rows)


def test_console_simulate_needs_role_and_simulation_mode(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    officer = login(client, OFFICER)
    created = client.post(
        "/api/v1/safety/simulate",
        headers=officer,
        json={"event_type": "fire_alarm", "canteen_id": "a", "note": "Demo run 1"},
    )
    assert created.status_code == 201
    event = created.json()["event"]
    assert (event["is_simulation"], event["note"], event["canteen_name"]) == (True, "Demo run 1", "Canteen A")
    assert client.post("/api/v1/safety/simulate", headers=login(client, MANAGER_A), json={}).status_code == 403
    assert client.post("/api/v1/safety/simulate", headers=officer, json={"canteen_id": "zz"}).status_code == 422
    monkeypatch.setattr(get_settings(), "simulation_mode", False)
    off = client.post("/api/v1/safety/simulate", headers=officer, json={})
    assert (off.status_code, off.json()["error"]["code"]) == (403, "simulation_disabled")


def test_heartbeat_loss_warns_officers_only(client: TestClient, seeded: Engine) -> None:
    assert send(client, {"status": "ok"}, path="/api/v1/safety/heartbeat").status_code == 200
    sources = client.get("/api/v1/safety/sources", headers=login(client, OFFICER)).json()["items"]
    assert next(s for s in sources if s["id"] == "safety-sim")["state"] == "online"
    with Session(seeded) as s:
        assert check_sources(s, LUNCH_NOW + timedelta(seconds=59)) == []
        warned = check_sources(s, LUNCH_NOW + timedelta(seconds=61))
        s.commit()
        assert [(e.event_type, e.severity, e.is_simulation) for e in warned] == [
            ("integration_offline", "warning", True)
        ]
        assert check_sources(s, LUNCH_NOW + timedelta(seconds=90)) == []
    assert client.get("/api/v1/safety/active").json()["active"] is False
    staff = client.get("/api/v1/safety/events", headers=login(client, OFFICER)).json()["items"]
    assert [e["title"] for e in staff] == ["Alarm integration offline (simulated)"]
    with Session(seeded) as s:
        source = s.get(SafetySource, "safety-sim")
        assert source is not None
        source.last_heartbeat_at = LUNCH_NOW + timedelta(seconds=120)
        s.commit()
        resolved = check_sources(s, LUNCH_NOW + timedelta(seconds=125))
        s.commit()
        assert [(e.status, e.resolution_note) for e in resolved] == [("resolved", "Heartbeat resumed.")]


def test_approved_integration_can_send_real_events_with_approved_text(client: TestClient, seeded: Engine) -> None:
    with Session(seeded) as s:
        s.add(
            SafetySource(
                id="gw-test",
                name="Approved gateway (test)",
                kind="approved_integration",
                token_hash=hash_token(GATEWAY_TOKEN),
            )
        )
        s.add(
            SafetyInstruction(
                canteen_id="a",
                event_type="fire_alarm",
                body="Sample approved text for tests.",
                approved_by_name="Test approver",
                approved_at=LUNCH_NOW,
                is_active=True,
            )
        )
        s.commit()
    real = send(client, alarm(event_id="gw-1", claims_simulation=False), token=GATEWAY_TOKEN).json()
    assert (real["is_simulation"], real["label"]) == (False, None)
    event = client.get("/api/v1/safety/active").json()["events"][0]
    assert (event["title"], event["instructions"]) == ("Fire alarm", "Sample approved text for tests.")
    simulated = send(client, alarm(event_id="gw-2"), token=GATEWAY_TOKEN).json()
    assert simulated["merged"] is False and simulated["is_simulation"] is True
