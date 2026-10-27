from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.main import app
from tests.integration.conftest import LUNCH_NOW, client_at


def by_id(items: list[dict[str, Any]], key: str = "id") -> dict[str, dict[str, Any]]:
    return {item[key]: item for item in items}


def test_student_summary_matches_sample_design(api: TestClient) -> None:
    body = api.get("/api/v1/student/summary").json()
    assert body["best"] == {"canteen_id": "b", "name": "Canteen B"}
    canteens = by_id(body["canteens"])
    a, b, c = canteens["a"], canteens["b"], canteens["c"]
    assert (a["level"], a["percent"], a["free_about"], a["free_range"]) == ("busy", 79, 16, [10, 23])
    assert (a["zones_live"], a["zones_total"], a["monitored_capacity"]) == (2, 3, 76)
    assert (b["level"], b["percent"], b["free_about"], b["free_range"]) == ("normal", 47, 32, [26, 38])
    assert (c["level"], c["percent"], c["free_about"], c["free_range"]) == ("crowded", 88, 9, [5, 13])
    assert [(x["shops_open"], x["shops_total"]) for x in (a, b, c)] == [(3, 4), (2, 3), (1, 2)]
    assert a["walk"] == {"from_name": "Canteen B", "minutes": 4}
    assert body["safety"] == {"active": False, "events": []}
    assert body["busy_today"] is None
    assert len(body["shops_now"]) == 4


def test_canteen_detail_hides_numbers_for_offline_zone(api: TestClient) -> None:
    body = api.get("/api/v1/canteens/a").json()
    zones = body["zones"]
    assert [z["name"] for z in zones] == ["Indoor hall", "Terrace", "Balcony"]
    assert (zones[0]["percent"], zones[0]["level"], zones[0]["free_range"]) == (83, "crowded", [3, 9])
    balcony = zones[2]
    assert (balcony["freshness"], balcony["percent"], balcony["free_about"]) == ("unavailable", None, None)
    assert body["hours_today"] == [{"opens": "07:00", "closes": "18:00"}]
    assert [s["name"] for s in body["shops"]][:2] == ["Rice & Curry Stall", "Kottu Corner"]


def test_zone_occupancy_endpoint(api: TestClient) -> None:
    body = api.get("/api/v1/canteens/b/occupancy").json()
    assert body["canteen_id"] == "b"
    assert [z["free_about"] for z in body["zones"]] == [18, 14]


def test_shop_statuses(api: TestClient) -> None:
    shops = by_id(api.get("/api/v1/canteens/b/shops").json()["items"])
    noodle = shops["s-noodle"]["status"]
    assert (noodle["state"], noodle["closes_at_local"], noodle["reason"]) == (
        "closes_soon",
        "13:00",
        "earlier than usual today",
    )
    assert shops["s-smoothie"]["status"]["opens_at_local"] == "15:00"
    juice = by_id(api.get("/api/v1/canteens/c/shops").json()["items"])["s-juice"]["status"]
    assert (juice["state"], juice["reason"]) == ("temporarily_closed", "Restocking — back tomorrow")
    rice = by_id(api.get("/api/v1/canteens/a/shops").json()["items"])["s-rice"]
    assert rice["hours_label"] == "Mon–Fri 7:00 a.m.–3:00 p.m."


def test_menu_with_period_filter(api: TestClient) -> None:
    full = api.get("/api/v1/shops/s-rice/menu").json()
    assert len(full["items"]) == 8
    lunch = api.get("/api/v1/shops/s-rice/menu", params={"period": "lunch"}).json()["items"]
    assert len(lunch) == 6
    items = by_id(lunch, "name")
    assert items["Vegetable rice & curry"]["price_lkr"] == 350
    assert items["Vegetable rice & curry"]["tags"] == ["rice", "vegetarian"]
    assert items["Fish rice & curry"]["is_available"] is False
    assert api.get("/api/v1/shops/s-tea/menu").json()["items"] == []


def test_meal_status_during_lunch(api: TestClient) -> None:
    body = api.get("/api/v1/meal-status").json()
    assert body["state"] == "active"
    assert body["current"]["period"] == "lunch"
    assert body["current"]["ends"].startswith("2026-11-20T08:30:00")
    assert body["next"]["period"] == "dinner"
    kinds = [(d["weekday"], d["kind"]) for d in body["week"]]
    assert kinds[4] == ("Fri", "regular") and kinds[5] == ("Sat", "special") and kinds[6] == ("Sun", "closed")
    assert body["week"][4]["is_today"] is True


def test_errors_use_plan_format(api: TestClient) -> None:
    missing = api.get("/api/v1/canteens/zz")
    assert missing.status_code == 404
    body = missing.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["details"] == {"canteen_id": "zz"}
    assert body["request_id"].startswith("req_")
    assert missing.headers["X-Request-ID"] == body["request_id"]
    invalid = api.get("/api/v1/shops/s-rice/menu", params={"period": "brunch"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert api.get("/api/v1/meal-status", params={"canteen_id": "zz"}).status_code == 404


def test_data_goes_stale_then_unavailable(seeded: Engine) -> None:
    with client_at(seeded, LUNCH_NOW + timedelta(minutes=5)) as client:
        a = by_id(client.get("/api/v1/student/summary").json()["canteens"])["a"]
        assert (a["freshness"], a["level"], a["free_about"]) == ("stale", "unknown", 16)
    with client_at(seeded, LUNCH_NOW + timedelta(minutes=15)) as client:
        body = client.get("/api/v1/student/summary").json()
        a = by_id(body["canteens"])["a"]
        assert (a["freshness"], a["percent"], a["free_about"], a["free_range"]) == ("unavailable", None, None, None)
        assert body["best"] is None
    app.dependency_overrides.clear()
