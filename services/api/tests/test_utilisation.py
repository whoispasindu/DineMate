from datetime import UTC, datetime, timedelta

from app.services.utilisation import ZoneSlot, summarise

NOON = datetime(2026, 11, 20, 6, 30, tzinfo=UTC)


def always_open(_canteen: str, _at: datetime) -> bool:
    return True


def test_seat_hours_and_empty_zone_hours() -> None:
    slots = [
        ZoneSlot("a", "z1", NOON + timedelta(minutes=10 * i), occupied, 30) for i, occupied in enumerate([30, 15, 0, 1])
    ]
    result = summarise(slots, always_open)
    (a,) = result.canteens
    assert (a.seat_hours_used, a.seat_hours_available) == (7.7, 20.0)
    assert a.empty_zone_hours == 0.3
    assert a.utilisation is not None and round(a.utilisation, 3) == 0.385


def test_closed_slots_are_ignored_and_peak_balance_is_measured() -> None:
    slots = [
        ZoneSlot("a", "z1", NOON, 27, 30),
        ZoneSlot("b", "z2", NOON, 9, 30),
        ZoneSlot("a", "z1", NOON - timedelta(hours=3), 0, 30),
    ]
    result = summarise(slots, lambda _c, at: at >= NOON - timedelta(hours=1))
    assert [c.empty_zone_hours for c in result.canteens] == [0.0, 0.0]
    assert result.peak_days == 1 and result.peak_cv == 0.5


def test_one_canteen_has_no_balance_figure() -> None:
    assert summarise([ZoneSlot("a", "z1", NOON, 5, 30)], always_open).peak_cv is None
