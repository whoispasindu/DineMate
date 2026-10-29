from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app import models
from app.core.security import REFRESH_COOKIE
from app.main import app
from app.seed import reset, seed
from app.services.rules import evaluate
from tests.integration.conftest import LUNCH_NOW, TEST_PASSWORD, client_at, login

ADMIN = "admin@dinemate.test"
MANAGER_A = "canteen.a@dinemate.test"
RICE = "rice.stall@dinemate.test"


@pytest.fixture
def db(seeded: Engine) -> Iterator[Engine]:
    yield seeded
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


@pytest.fixture
def client(db: Engine) -> Iterator[TestClient]:
    with client_at(db, LUNCH_NOW) as c:
        yield c


def refresh_with(client: TestClient, token: str) -> int:
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, token)
    return client.post("/api/v1/auth/refresh").status_code


def test_login_me_and_wrong_password(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "Admin@DineMate.test", "password": TEST_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900
    assert body["user"]["role"] == "campus_admin"
    cookie = response.headers["set-cookie"]
    assert REFRESH_COOKIE in cookie and "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    assert me["email"] == ADMIN
    manager = client.get("/api/v1/auth/me", headers=login(client, MANAGER_A)).json()
    assert manager["canteen_ids"] == ["a"]
    for bad in ({"email": ADMIN, "password": "nope"}, {"email": "nobody@dinemate.test", "password": "nope"}):
        failed = client.post("/api/v1/auth/login", json=bad)
        assert (failed.status_code, failed.json()["error"]["code"]) == (401, "invalid_credentials")
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_login_rate_limit(client: TestClient) -> None:
    codes = [client.post("/api/v1/auth/login", json={"email": ADMIN, "password": "x"}).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]


def test_refresh_rotates_and_reuse_revokes_everything(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": ADMIN, "password": TEST_PASSWORD})
    first = client.cookies.get(REFRESH_COOKIE)
    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200 and rotated.json()["user"]["email"] == ADMIN
    second = client.cookies.get(REFRESH_COOKIE)
    assert second and second != first
    assert refresh_with(client, first or "") == 401
    assert refresh_with(client, second) == 401


def test_logout_revokes_refresh(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": ADMIN, "password": TEST_PASSWORD})
    token = client.cookies.get(REFRESH_COOKIE)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert refresh_with(client, token or "") == 401


def test_disabled_user_cannot_sign_in_or_use_token(client: TestClient, db: Engine) -> None:
    headers = login(client, RICE)
    with Session(db) as s:
        user = s.scalars(select(models.User).where(models.User.email == RICE)).one()
        user.is_active = False
        s.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": RICE, "password": TEST_PASSWORD}).status_code == 401


def test_roles_and_canteen_scope_on_alerts(db: Engine) -> None:
    t = LUNCH_NOW
    with Session(db) as s:
        zones = {
            z.name + z.canteen_id: z
            for z in s.scalars(select(models.SeatingZone).where(models.SeatingZone.canteen_id.in_(["a", "c"])))
        }
        for i in range(1, 6):
            at = t + timedelta(seconds=30 * i)
            for key, device in (("Main hallc", "sim-c"), ("Indoor halla", "sim-a")):
                z = zones[key]
                s.add(
                    models.OccupancyReading(
                        zone_id=z.id,
                        device_id=device,
                        captured_at=at,
                        estimated_occupied=z.capacity - 4,
                        occupied_low=z.capacity - 6,
                        occupied_high=z.capacity - 2,
                        capacity_snapshot=z.capacity,
                        confidence="medium",
                        is_simulated=True,
                    )
                )
            s.commit()
            evaluate(s, at)
    with client_at(db, t + timedelta(seconds=150)) as client:
        assert client.get("/api/v1/alerts", headers=login(client, RICE)).status_code == 403
        manager = login(client, MANAGER_A)
        seen = client.get("/api/v1/alerts", headers=manager).json()["items"]
        assert [a["title"] for a in seen] == ["Canteen A — Indoor hall"]
        admin = login(client, ADMIN)
        everything = client.get("/api/v1/alerts", headers=admin).json()["items"]
        c_alert = next(a for a in everything if a["title"] == "Canteen C — Main hall")
        denied = client.post(f"/api/v1/alerts/{c_alert['id']}/acknowledge", headers=manager)
        assert (denied.status_code, denied.json()["error"]["code"]) == (403, "forbidden_scope")
        own = client.post(f"/api/v1/alerts/{seen[0]['id']}/acknowledge", headers=manager).json()
        assert own["acknowledged_by"] == "Canteen A manager"
    with Session(db) as s:
        actions = [row.action for row in s.scalars(select(models.AuditLog).order_by(models.AuditLog.id))]
        assert "auth.login" in actions and actions[-1] == "alert.acknowledge"
