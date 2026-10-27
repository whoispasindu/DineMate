from datetime import date, datetime, time

from app.services.meal_status import Override, ScheduleBook, WeeklySlot, meal_status
from app.services.timeutil import CAMPUS_TZ

REGULAR = [("breakfast", time(7), time(9, 30)), ("lunch", time(11, 30), time(14)), ("dinner", time(18), time(20, 30))]


def campus_week() -> list[WeeklySlot]:
    slots = [WeeklySlot(None, wd, p, s, e) for wd in range(5) for p, s, e in REGULAR]
    slots.append(WeeklySlot(None, 5, "lunch", time(11, 30), time(13, 30)))
    return slots


def at(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, second, tzinfo=CAMPUS_TZ)


def local_hm(dt: datetime) -> str:
    return dt.astimezone(CAMPUS_TZ).strftime("%a %H:%M")


def test_lunch_is_active_with_dinner_next() -> None:
    state = meal_status(at(20, 12, 41, 18), ScheduleBook(campus_week(), []))
    assert state.state == "active"
    assert state.current is not None and state.current.period == "lunch"
    assert local_hm(state.current.ends) == "Fri 14:00"
    assert state.next is not None and state.next.period == "dinner"


def test_upcoming_between_meals() -> None:
    state = meal_status(at(20, 10, 0), ScheduleBook(campus_week(), []))
    assert state.state == "upcoming"
    assert state.current is None
    assert state.next is not None and local_hm(state.next.starts) == "Fri 11:30"


def test_midnight_rollover_points_to_next_breakfast() -> None:
    state = meal_status(at(19, 23, 59), ScheduleBook(campus_week(), []))
    assert state.next is not None and local_hm(state.next.starts) == "Fri 07:00"


def test_weekend_gap_skips_closed_sunday() -> None:
    state = meal_status(at(21, 14, 0), ScheduleBook(campus_week(), []))
    assert state.state == "upcoming"
    assert state.next is not None and local_hm(state.next.starts) == "Mon 07:00"
    assert state.today and state.today[0].period == "lunch"


def test_campus_holiday_cancels_the_day() -> None:
    holiday = Override(None, date(2026, 11, 20), None, True, None, None, "Poya holiday")
    state = meal_status(at(20, 12, 0), ScheduleBook(campus_week(), [holiday]))
    assert state.today == []
    assert state.next is not None and local_hm(state.next.starts) == "Sat 11:30"
    friday = next(d for d in state.week if d.day == date(2026, 11, 20))
    assert friday.kind == "closed"
    assert friday.note == "Poya holiday"


def test_canteen_override_beats_campus_weekly() -> None:
    extended = Override("a", date(2026, 11, 20), "lunch", False, time(11, 30), time(15), "Exam week")
    state = meal_status(at(20, 14, 30), ScheduleBook(campus_week(), [extended], canteen_id="a"))
    assert state.current is not None and local_hm(state.current.ends) == "Fri 15:00"
    other = meal_status(at(20, 14, 30), ScheduleBook(campus_week(), [extended], canteen_id="b"))
    assert other.current is None


def test_canteen_weekly_beats_campus_override() -> None:
    own_week = [WeeklySlot("a", wd, p, s, e) for wd in range(7) for p, s, e in REGULAR]
    holiday = Override(None, date(2026, 11, 20), None, True, None, None, "Campus holiday")
    state = meal_status(at(20, 12, 0), ScheduleBook(campus_week() + own_week, [holiday], canteen_id="a"))
    assert state.current is not None and state.current.period == "lunch"


def test_week_marks_saturday_special_and_sunday_closed() -> None:
    state = meal_status(at(20, 12, 0), ScheduleBook(campus_week(), []))
    kinds = {d.day.weekday(): (d.kind, d.note) for d in state.week}
    assert kinds[0] == ("regular", None)
    assert kinds[5] == ("special", "special hours — lunch only, 11:30 a.m. – 1:30 p.m.")
    assert kinds[6] == ("closed", "canteens closed")
    assert [d.is_today for d in state.week].index(True) == 4


def test_no_schedule_means_none() -> None:
    state = meal_status(at(20, 12, 0), ScheduleBook([], []))
    assert state.state == "none"
    assert state.next is None
