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

RICE = "rice.stall@dinemate.test"
MANAGER_A = "canteen.a@dinemate.test"
ADMIN = "admin@dinemate.test"


@pytest.fixture
def client(seeded: Engine) -> Iterator[TestClient]:
    with client_at(seeded, LUNCH_NOW) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(seeded) as session:
        reset(session)
        seed(session, LUNCH_NOW, TEST_PASSWORD)


def public_menu(client: TestClient, shop_id: str = "s-rice") -> dict[str, dict]:
    return {i["name"]: i for i in client.get(f"/api/v1/shops/{shop_id}/menu").json()["items"]}


def item_id(editor: dict, name: str) -> str:
    return next(i["id"] for i in editor["items"] if (i["draft"] or i["live"])["name"] == name)


def test_sold_out_is_instant_and_scoped(client: TestClient, seeded: Engine) -> None:
    rice = login(client, RICE)
    listed = client.get("/api/v1/manage/shops", headers=rice).json()["items"]
    assert [s["shop"]["id"] for s in listed] == ["s-rice"]
    editor = client.get("/api/v1/manage/shops/s-rice", headers=rice).json()
    veg = item_id(editor, "Vegetable rice & curry")
    assert public_menu(client)["Vegetable rice & curry"]["is_available"] is True

    result = client.patch(f"/api/v1/menu-items/{veg}/availability", headers=rice, json={"is_available": False})
    assert result.status_code == 200 and result.json()["item"]["is_available"] is False
    assert public_menu(client)["Vegetable rice & curry"]["is_available"] is False

    kottu_editor = client.get("/api/v1/manage/shops/s-kottu", headers=login(client, ADMIN)).json()
    chicken_kottu = item_id(kottu_editor, "Chicken kottu")
    denied = [
        client.get("/api/v1/manage/shops/s-kottu", headers=rice),
        client.patch(f"/api/v1/menu-items/{chicken_kottu}/availability", headers=rice, json={"is_available": False}),
        client.put("/api/v1/shops/s-kottu/hours", headers=rice, json={"weekly": [], "exceptions": []}),
        client.post("/api/v1/shops/s-kottu/menu/publish", headers=rice),
        client.get("/api/v1/manage/shops/s-noodle", headers=login(client, MANAGER_A)),
    ]
    assert [(r.status_code, r.json()["error"]["code"]) for r in denied] == [(403, "forbidden_scope")] * 5
    assert client.get("/api/v1/manage/shops", headers=login(client, "safety@dinemate.test")).status_code == 403
    assert client.get("/api/v1/manage/shops").status_code == 401

    with Session(seeded) as s:
        rows = list(s.scalars(select(models.AuditLog).where(models.AuditLog.action == "menu_item.availability")))
        assert [(r.entity_id, r.after) for r in rows] == [(veg, {"is_available": False})]


def test_draft_then_publish(client: TestClient) -> None:
    rice = login(client, RICE)
    editor = client.get("/api/v1/manage/shops/s-rice", headers=rice).json()
    chicken = item_id(editor, "Chicken rice & curry")
    egg = item_id(editor, "Egg fried rice")

    created = client.post(
        "/api/v1/shops/s-rice/menu-items",
        headers=rice,
        json={"name": "Sample jackfruit curry rice", "price_lkr": "390.00", "category": "rice", "periods": ["lunch"]},
    )
    assert created.status_code == 201
    edited = client.patch(f"/api/v1/menu-items/{chicken}", headers=rice, json={"price_lkr": 470}).json()
    removed = client.delete(f"/api/v1/menu-items/{egg}", headers=rice).json()
    assert edited["pending_changes"] == 2 and removed["pending_changes"] == 3
    pending = {i["id"]: i["pending"] for i in removed["items"]}
    assert (pending[chicken], pending[egg]) == ("edit", "delete")

    before = public_menu(client)
    assert before["Chicken rice & curry"]["price_lkr"] == 450
    assert "Sample jackfruit curry rice" not in before and "Egg fried rice" in before

    published = client.post("/api/v1/shops/s-rice/menu/publish", headers=rice).json()
    assert published["pending_changes"] == 0
    after = public_menu(client)
    assert after["Chicken rice & curry"]["price_lkr"] == 470
    assert after["Sample jackfruit curry rice"]["periods"] == ["lunch"]
    assert "Egg fried rice" not in after
    assert published["shop"]["menu_updated_at"] is not None

    reverted = client.patch(f"/api/v1/menu-items/{chicken}", headers=rice, json={"price_lkr": 500}).json()
    assert reverted["pending_changes"] == 1
    same = client.patch(f"/api/v1/menu-items/{chicken}", headers=rice, json={"price_lkr": 470}).json()
    assert same["pending_changes"] == 0
    client.patch(f"/api/v1/menu-items/{chicken}", headers=rice, json={"name": "Sample chicken curry rice"})
    discarded = client.post("/api/v1/shops/s-rice/menu/discard", headers=rice).json()
    assert discarded["pending_changes"] == 0 and "Chicken rice & curry" in public_menu(client)


def test_price_validation(client: TestClient) -> None:
    rice = login(client, RICE)
    for price in (-1, 100_001, "12.345"):
        bad = client.post(
            "/api/v1/shops/s-rice/menu-items",
            headers=rice,
            json={"name": "Sample", "price_lkr": price, "periods": ["lunch"]},
        )
        assert bad.status_code == 422
    no_period = client.post(
        "/api/v1/shops/s-rice/menu-items", headers=rice, json={"name": "Sample", "price_lkr": 100, "periods": []}
    )
    assert no_period.status_code == 422


def test_hours_and_closure(client: TestClient) -> None:
    manager = login(client, MANAGER_A)
    hours = {
        "weekly": [
            {"weekday": d, "opens": o, "closes": c}
            for d in range(5)
            for o, c in (("07:00", "10:30"), ("11:30", "15:00"))
        ],
        "exceptions": [{"date": "2026-12-25", "is_closed": True, "reason": "Sample holiday"}],
    }
    saved = client.put("/api/v1/shops/s-rice/hours", headers=manager, json=hours)
    assert saved.status_code == 200
    body = saved.json()
    assert len(body["weekly"]) == 10 and body["exceptions"][0]["is_closed"] is True
    assert body["shop"]["status"]["state"] == "open"

    overlap = {
        "weekly": [
            {"weekday": 0, "opens": "07:00", "closes": "12:00"},
            {"weekday": 0, "opens": "11:00", "closes": "15:00"},
        ],
        "exceptions": [],
    }
    backwards = {"weekly": [{"weekday": 0, "opens": "15:00", "closes": "07:00"}], "exceptions": []}
    special = {"weekly": [], "exceptions": [{"date": "2026-12-24", "is_closed": False}]}
    for bad in (overlap, backwards, special):
        assert client.put("/api/v1/shops/s-rice/hours", headers=manager, json=bad).status_code == 422

    until = (LUNCH_NOW + timedelta(hours=1)).isoformat()
    closed = client.put("/api/v1/shops/s-rice/closure", headers=manager, json={"until": until, "reason": "Gas refill"})
    status = closed.json()["shop"]["status"]
    assert (status["state"], status["reason"]) == ("temporarily_closed", "Gas refill")
    past = (LUNCH_NOW - timedelta(minutes=1)).isoformat()
    assert client.put("/api/v1/shops/s-rice/closure", headers=manager, json={"until": past}).status_code == 422
    reopened = client.put("/api/v1/shops/s-rice/closure", headers=manager, json={"until": None}).json()
    assert reopened["shop"]["status"]["state"] == "open" and reopened["closure_reason"] is None
