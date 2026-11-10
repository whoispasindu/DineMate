import os
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app import models
from app.core.config import Settings, get_settings
from app.core.security import hash_refresh_token, login_limiter
from app.main import app
from app.seed import reset, seed
from app.services.retention import purge_old_data
from app.testfeeds.storage import purge_orphans
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at

SIM = {"Authorization": "Device dev-simulator-token"}
ADMIN = "admin@dinemate.test"


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def attempt(client: TestClient, password: str, email: str = ADMIN) -> int:
    login_limiter.reset()
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).status_code


def test_an_account_locks_after_repeated_wrong_passwords(client: TestClient, seeded: Engine) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(login_failures_before_lock=3)
    assert [attempt(client, "wrong") for _ in range(3)] == [401, 401, 401]
    assert attempt(client, TEST_PASSWORD) == 429
    assert attempt(client, TEST_PASSWORD, "canteen.a@dinemate.test") == 200
    assert [attempt(client, "x", "nobody@dinemate.test") for _ in range(4)] == [401, 401, 401, 429]
    with Session(seeded) as session:
        for row in session.scalars(select(models.LoginThrottle)):
            row.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert attempt(client, TEST_PASSWORD) == 200
    with Session(seeded) as session:
        assert session.scalar(select(func.count()).select_from(models.LoginThrottle)) == 1


def test_only_cameras_report_local_live_addresses(client: TestClient) -> None:
    beat = {"status": "ok", "stream_url": "http://192.168.1.20:8090/live"}
    refused = client.post("/api/v1/devices/sim-a/heartbeat", headers=SIM, json=beat)
    assert refused.status_code == 422
    assert client.post("/api/v1/devices/sim-a/heartbeat", headers=SIM, json={"status": "ok"}).status_code == 200


def test_old_data_is_removed_and_recent_data_kept(seeded: Engine) -> None:
    settings = Settings()
    now = LUNCH_NOW
    with Session(seeded) as session:
        zone = session.scalars(select(models.SeatingZone)).first()
        user = session.scalars(select(models.User)).first()
        assert zone is not None and user is not None
        for age in (100, 5):
            at = now - timedelta(days=age)
            session.add(
                models.OccupancyReading(
                    zone_id=zone.id,
                    device_id="sim-a",
                    captured_at=at,
                    received_at=at,
                    estimated_occupied=1,
                    occupied_low=1,
                    occupied_high=1,
                    capacity_snapshot=10,
                    confidence="high",
                    is_simulated=True,
                )
            )
            session.add(models.DeviceHeartbeat(device_id="sim-a", received_at=at, status="ok", stream_ok=True))
            session.add(
                models.SeatSession(
                    zone_id=zone.id,
                    seat_id=f"old-{age}",
                    state="occupied",
                    started_at=at,
                    ended_at=at,
                    is_simulated=True,
                )
            )
        for name, expires in (("stale", now - timedelta(days=3)), ("live", now + timedelta(days=3))):
            session.add(
                models.RefreshToken(
                    user_id=user.id,
                    token_hash=hash_refresh_token(name + uuid.uuid4().hex),
                    created_at=now,
                    expires_at=expires,
                )
            )
        session.flush()
        removed = purge_old_data(session, now, now, settings)
        assert removed["occupancy_readings"] >= 1 and removed["seat_sessions"] == 1
        assert removed["device_heartbeats"] == 1 and removed["refresh_tokens"] == 1
        kept = session.scalar(
            select(func.count())
            .select_from(models.OccupancyReading)
            .where(models.OccupancyReading.captured_at == now - timedelta(days=5))
        )
        assert kept == 1
        session.rollback()


def test_unused_uploads_are_deleted_after_an_hour(seeded: Engine, tmp_path: Path) -> None:
    settings = Settings(test_videos_dir=str(tmp_path))
    used, fresh, stale = tmp_path / "used-abcdef.mp4", tmp_path / "fresh-abcdef.mp4", tmp_path / "stale-abcdef.mp4"
    for path in (used, fresh, stale):
        path.write_bytes(b"x")
    old = time.time() - 7200
    os.utime(used, (old, old))
    os.utime(stale, (old, old))
    with Session(seeded) as session:
        session.add(
            models.Device(id="cam-keep", canteen_id="a", kind="camera", config={"source": "video:used-abcdef.mp4"})
        )
        session.flush()
        assert purge_orphans(session, settings, time.time()) == 1
        session.rollback()
    assert used.exists() and fresh.exists() and not stale.exists()
