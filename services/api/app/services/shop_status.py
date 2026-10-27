from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

from app.services.timeutil import WEEKDAY_SHORT, at_local, full_range, hm, local, local_date

CLOSES_SOON_MINUTES = 30

ShopState = Literal["open", "closes_soon", "closed", "temporarily_closed", "unknown"]
Interval = tuple[time, time]


@dataclass(frozen=True)
class HoursException:
    day: date
    is_closed: bool
    opens: time | None
    closes: time | None
    reason: str | None


@dataclass(frozen=True)
class ShopStatus:
    state: ShopState
    closes_at_local: str | None = None
    opens_at_local: str | None = None
    reason: str | None = None


def _intervals_today(
    today: date, weekly: dict[int, list[Interval]], exceptions: list[HoursException]
) -> tuple[list[Interval], str | None, bool]:
    todays = [e for e in exceptions if e.day == today]
    if todays:
        reason = next((e.reason for e in todays if e.reason), None)
        if any(e.is_closed for e in todays):
            return [], reason, True
        return sorted((e.opens, e.closes) for e in todays if e.opens and e.closes), reason, True
    return sorted(weekly.get(today.weekday(), [])), None, False


def shop_status(
    now: datetime,
    weekly: dict[int, list[Interval]],
    exceptions: list[HoursException],
    temporarily_closed_until: datetime | None = None,
    closure_reason: str | None = None,
) -> ShopStatus:
    if temporarily_closed_until is not None and temporarily_closed_until > now:
        return ShopStatus(state="temporarily_closed", reason=closure_reason)
    today = local_date(now)
    intervals, reason, from_exception = _intervals_today(today, weekly, exceptions)
    if not from_exception and not any(weekly.values()):
        return ShopStatus(state="unknown")
    now_local = local(now).time()
    for opens, closes in intervals:
        if opens <= now_local < closes:
            minutes_left = (at_local(today, closes) - now).total_seconds() / 60
            state: ShopState = "closes_soon" if minutes_left <= CLOSES_SOON_MINUTES else "open"
            return ShopStatus(state=state, closes_at_local=hm(closes), reason=reason)
        if now_local < opens:
            return ShopStatus(state="closed", opens_at_local=hm(opens), reason=reason)
    return ShopStatus(state="closed", reason=reason)


def hours_label(weekly: dict[int, list[Interval]]) -> str:
    groups: list[tuple[int, int, tuple[Interval, ...]]] = []
    for weekday in range(7):
        intervals = tuple(sorted(weekly.get(weekday, [])))
        if not intervals:
            continue
        if groups and groups[-1][2] == intervals and groups[-1][1] == weekday - 1:
            groups[-1] = (groups[-1][0], weekday, intervals)
        else:
            groups.append((weekday, weekday, intervals))
    if not groups:
        return "Hours not available"
    parts = []
    for first, last, intervals in groups:
        days = WEEKDAY_SHORT[first] if first == last else f"{WEEKDAY_SHORT[first]}–{WEEKDAY_SHORT[last]}"
        parts.append(f"{days} {', '.join(full_range(o, c) for o, c in intervals)}")
    return "; ".join(parts)
