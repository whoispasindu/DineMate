from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

CAMPUS_TZ = ZoneInfo("Asia/Colombo")
WEEKDAY_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def local(now: datetime) -> datetime:
    return now.astimezone(CAMPUS_TZ)


def local_date(now: datetime) -> date:
    return local(now).date()


def at_local(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=CAMPUS_TZ).astimezone(UTC)


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def hm(at: time) -> str:
    return at.strftime("%H:%M")


def twelve_hour(at: time, with_period: bool = True) -> str:
    hour = at.hour % 12 or 12
    text = f"{hour}:{at.minute:02d}"
    if not with_period:
        return text
    return f"{text} {'a.m.' if at.hour < 12 else 'p.m.'}"


def time_range(start: time, end: time, spaced: bool = True) -> str:
    same_period = (start.hour < 12) == (end.hour < 12)
    dash = " – " if spaced else "–"
    return f"{twelve_hour(start, not same_period)}{dash}{twelve_hour(end)}"


def full_range(start: time, end: time) -> str:
    return f"{twelve_hour(start)}–{twelve_hour(end)}"
