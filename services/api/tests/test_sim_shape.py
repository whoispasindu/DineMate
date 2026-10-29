import random
from datetime import UTC, datetime

from app.services.timeutil import CAMPUS_TZ
from app.sim import next_occupancy, target_for
from app.sim_shape import daily_shape


def at(hour: int, minute: int = 0, day: int = 20) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=CAMPUS_TZ).astimezone(UTC)


def test_lunch_peak_matches_the_seeded_base() -> None:
    assert abs(daily_shape(at(12, 45)) - 1.0) < 0.01
    assert target_for(43, at(12, 41)) == 43
    assert target_for(43, at(15, 30)) < 10
    assert daily_shape(at(12, 45, day=21)) < 0.5


def test_occupancy_walks_toward_a_moved_target() -> None:
    rng = random.Random(3)
    value = 40
    for _ in range(20):
        value = next_occupancy(value, 8, 48, rng)
    assert abs(value - 8) <= 4
    steady = [next_occupancy(20, 20, 48, rng) for _ in range(50)]
    assert all(16 <= v <= 24 for v in steady)
