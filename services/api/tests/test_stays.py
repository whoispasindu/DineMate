from datetime import UTC, datetime, timedelta

from app.services.stays import leave_chance, likely_to_free, median_by_hour, stay_minutes

NOON_COLOMBO = datetime(2026, 11, 20, 6, 30, tzinfo=UTC)


def test_stays_outside_one_minute_to_four_hours_are_ignored() -> None:
    assert stay_minutes(NOON_COLOMBO, NOON_COLOMBO + timedelta(seconds=30)) is None
    assert stay_minutes(NOON_COLOMBO, NOON_COLOMBO + timedelta(hours=5)) is None
    assert stay_minutes(NOON_COLOMBO, NOON_COLOMBO + timedelta(minutes=25)) == 25


def test_median_stay_is_grouped_by_campus_hour() -> None:
    sessions = [(NOON_COLOMBO, NOON_COLOMBO + timedelta(minutes=m)) for m in (10, 20, 30)]
    sessions.append((NOON_COLOMBO + timedelta(hours=1), NOON_COLOMBO + timedelta(hours=1, minutes=40)))
    assert median_by_hour(sessions) == {12: (20.0, 3), 13: (40.0, 1)}


def test_leave_chance_uses_people_who_stayed_as_long() -> None:
    durations = [15.0, 20.0, 25.0, 40.0]
    assert leave_chance(18, durations) == 2 / 3
    assert leave_chance(5, durations) == 1 / 4
    assert leave_chance(60, durations) == 0.5


def test_likely_to_free_adds_up_each_seat() -> None:
    durations = [15.0, 20.0, 25.0, 40.0]
    assert likely_to_free([18, 18, 18], durations) == 2
    assert likely_to_free([18], []) is None
