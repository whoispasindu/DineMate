from datetime import date, datetime, time

from app.services.shop_status import HoursException, hours_label, shop_status
from app.services.timeutil import CAMPUS_TZ

FRIDAY = date(2026, 11, 20)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=CAMPUS_TZ)


def weekdays(*intervals: tuple[time, time]) -> dict[int, list[tuple[time, time]]]:
    return {wd: list(intervals) for wd in range(5)}


SPLIT = weekdays((time(7), time(10, 30)), (time(11, 30), time(15)))


def test_open_with_closing_time() -> None:
    status = shop_status(at(12), SPLIT, [])
    assert (status.state, status.closes_at_local) == ("open", "15:00")


def test_closes_soon_within_30_minutes() -> None:
    assert shop_status(at(14, 31), SPLIT, []).state == "closes_soon"
    assert shop_status(at(14, 29), SPLIT, []).state == "open"


def test_split_shift_gap_shows_next_opening() -> None:
    status = shop_status(at(11), SPLIT, [])
    assert (status.state, status.opens_at_local) == ("closed", "11:30")


def test_after_hours_closed_for_today() -> None:
    status = shop_status(at(16), SPLIT, [])
    assert (status.state, status.opens_at_local) == ("closed", None)


def test_temporary_closure_wins_over_hours() -> None:
    status = shop_status(at(12), SPLIT, [], datetime(2026, 11, 21, 7, tzinfo=CAMPUS_TZ), "Restocking")
    assert (status.state, status.reason) == ("temporarily_closed", "Restocking")


def test_expired_temporary_closure_is_ignored() -> None:
    assert shop_status(at(12), SPLIT, [], datetime(2026, 11, 20, 8, tzinfo=CAMPUS_TZ)).state == "open"


def test_exception_hours_replace_weekly() -> None:
    early = HoursException(FRIDAY, False, time(11), time(13), "earlier than usual today")
    status = shop_status(at(12, 41), SPLIT, [early])
    assert (status.state, status.closes_at_local, status.reason) == ("closes_soon", "13:00", "earlier than usual today")


def test_exception_closed_day() -> None:
    holiday = HoursException(FRIDAY, True, None, None, "Holiday")
    assert shop_status(at(12), SPLIT, [holiday]).state == "closed"


def test_no_hours_is_unknown_never_open() -> None:
    assert shop_status(at(12), {}, []).state == "unknown"


def test_weekend_closed_when_weekday_only() -> None:
    saturday = datetime(2026, 11, 21, 12, tzinfo=CAMPUS_TZ)
    assert shop_status(saturday, SPLIT, []).state == "closed"


def test_hours_label_groups_consecutive_days() -> None:
    assert hours_label(weekdays((time(7), time(15)))) == "Mon–Fri 7:00 a.m.–3:00 p.m."
    mixed = {**weekdays((time(7), time(15))), 5: [(time(8), time(12))]}
    assert hours_label(mixed) == "Mon–Fri 7:00 a.m.–3:00 p.m.; Sat 8:00 a.m.–12:00 p.m."
    assert hours_label({}) == "Hours not available"
