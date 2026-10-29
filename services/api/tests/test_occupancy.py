from datetime import UTC, datetime, timedelta

from app.services.occupancy import (
    Reading,
    best_candidate,
    canteen_occupancy,
    freshness_for,
    level_for,
    rank_alternatives,
    zone_view,
)

NOW = datetime(2026, 11, 20, 7, 11, 18, tzinfo=UTC)


def reading(occupied: int, low: int, high: int, capacity: int, age_s: int = 40) -> Reading:
    return Reading(NOW - timedelta(seconds=age_s), occupied, low, high, capacity)


def test_freshness_boundaries() -> None:
    assert freshness_for(NOW - timedelta(seconds=120), NOW) == "live"
    assert freshness_for(NOW - timedelta(seconds=121), NOW) == "stale"
    assert freshness_for(NOW - timedelta(seconds=600), NOW) == "stale"
    assert freshness_for(NOW - timedelta(seconds=601), NOW) == "unavailable"
    assert freshness_for(None, NOW) == "unavailable"


def test_level_thresholds() -> None:
    assert [level_for(p) for p in (59.9, 60, 79.9, 80, 95)] == ["normal", "busy", "busy", "crowded", "near_capacity"]


def test_live_zone_has_numbers_and_level() -> None:
    zone = zone_view("z", "Indoor hall", 36, reading(30, 27, 33, 36), NOW)
    assert (zone.percent, zone.free_about, zone.free_range, zone.level) == (83, 6, (3, 9), "crowded")


def test_stale_zone_keeps_numbers_but_no_level() -> None:
    zone = zone_view("z", "Indoor hall", 36, reading(30, 27, 33, 36, age_s=300), NOW)
    assert zone.freshness == "stale"
    assert zone.level == "unknown"
    assert zone.free_about == 6


def test_unavailable_zone_hides_numbers() -> None:
    zone = zone_view("z", "Balcony", 24, reading(10, 8, 12, 24, age_s=858), NOW)
    assert (zone.freshness, zone.percent, zone.free_about, zone.free_range) == ("unavailable", None, None, None)
    assert zone.updated_at is not None


def test_capacity_snapshot_is_used_for_percent() -> None:
    zone = zone_view("z", "Terrace", 50, reading(30, 26, 33, 40), NOW)
    assert (zone.capacity, zone.percent) == (40, 75)


def test_canteen_aggregates_counted_zones_only() -> None:
    zones = [
        zone_view("a1", "Indoor hall", 36, reading(30, 27, 33, 36), NOW),
        zone_view("a2", "Terrace", 40, reading(30, 26, 33, 40), NOW),
        zone_view("a3", "Balcony", 24, None, NOW),
    ]
    canteen = canteen_occupancy(zones)
    assert (canteen.percent, canteen.free_about, canteen.free_range) == (79, 16, (10, 23))
    assert (canteen.level, canteen.monitored_capacity, canteen.zones_live, canteen.zones_total) == ("busy", 76, 2, 3)


def test_canteen_without_data_is_unavailable() -> None:
    canteen = canteen_occupancy([zone_view("c1", "Hall", 48, None, NOW)])
    assert (canteen.freshness, canteen.level, canteen.free_about) == ("unavailable", "unknown", None)


def test_best_prefers_most_free_seats_among_not_crowded_live() -> None:
    def summary(occupied: int, low: int, high: int, capacity: int, age_s: int = 40):
        return canteen_occupancy([zone_view("z", "Zone", capacity, reading(occupied, low, high, capacity, age_s), NOW)])

    candidates = [
        ("a", summary(60, 53, 66, 76)),
        ("b", summary(28, 22, 34, 60)),
        ("c", summary(63, 59, 67, 72)),
        ("d", summary(5, 3, 7, 60, age_s=300)),
    ]
    assert best_candidate(candidates) == "b"
    assert best_candidate([("c", summary(63, 59, 67, 72))]) is None


def test_rank_alternatives_breaks_ties_by_walk_and_explains_exclusions() -> None:
    def summary(occupied: int, low: int, high: int, capacity: int, age_s: int = 40):
        return canteen_occupancy([zone_view("z", "Zone", capacity, reading(occupied, low, high, capacity, age_s), NOW)])

    candidates = [
        ("a", summary(28, 22, 34, 60)),
        ("b", summary(28, 22, 34, 60)),
        ("c", summary(63, 59, 67, 72)),
        ("d", summary(5, 3, 7, 60, age_s=300)),
    ]
    ranked, excluded = rank_alternatives(candidates, {"a": 6, "b": 4})
    assert ranked == ["b", "a"]
    assert excluded == {"c": "too_crowded", "d": "no_live_data"}
