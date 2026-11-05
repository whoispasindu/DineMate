import random
from datetime import UTC, datetime

from app.sim import seat_summary

LUNCH = datetime(2026, 11, 20, 7, 0, tzinfo=UTC)


def test_seat_summary_adds_up_to_capacity() -> None:
    summary = seat_summary("z", 40, 30, LUNCH, random.Random(1))
    total = summary["free"] + summary["occupied"] + summary["held"] + summary["unknown"]
    assert total == 40
    assert summary["held"] > 0
    assert not summary["crowded"]


def test_crowded_zone_hides_some_seats_and_never_goes_negative() -> None:
    summary = seat_summary("z", 40, 39, LUNCH, random.Random(2))
    assert summary["crowded"]
    assert summary["unknown"] == 1
    assert summary["free"] == 0
    assert summary["standing"] >= 3
