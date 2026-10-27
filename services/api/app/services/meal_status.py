from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Literal

from app.services.timeutil import WEEKDAY_SHORT, at_local, local_date, monday_of, time_range

PERIOD_ORDER = ("breakfast", "lunch", "dinner")
LOOKAHEAD_DAYS = 8


@dataclass(frozen=True)
class WeeklySlot:
    canteen_id: str | None
    weekday: int
    period: str
    starts: time
    ends: time


@dataclass(frozen=True)
class Override:
    canteen_id: str | None
    day: date
    period: str | None
    is_cancelled: bool
    starts: time | None
    ends: time | None
    reason: str | None


@dataclass(frozen=True)
class Window:
    period: str
    starts: datetime
    ends: datetime


@dataclass(frozen=True)
class DayPlan:
    slots: dict[str, tuple[time, time]]
    overridden: bool
    reason: str | None


@dataclass(frozen=True)
class WeekDayInfo:
    day: date
    kind: Literal["regular", "special", "closed"]
    note: str | None
    is_today: bool


@dataclass(frozen=True)
class MealState:
    state: Literal["active", "upcoming", "none"]
    current: Window | None
    next: Window | None
    today: list[Window]
    week: list[WeekDayInfo]


@dataclass
class ScheduleBook:
    weekly: list[WeeklySlot]
    overrides: list[Override]
    canteen_id: str | None = None
    _regular: tuple[tuple[str, time, time], ...] | None = field(default=None, init=False)

    def _weekly_for(self, owner: str | None, weekday: int) -> dict[str, tuple[time, time]]:
        return {s.period: (s.starts, s.ends) for s in self.weekly if s.canteen_id == owner and s.weekday == weekday}

    def _owner_has_weekly(self, owner: str | None) -> bool:
        return any(s.canteen_id == owner for s in self.weekly)

    def _patch(
        self, slots: dict[str, tuple[time, time]], owner: str | None, day: date
    ) -> tuple[dict[str, tuple[time, time]], bool, str | None]:
        patched = dict(slots)
        touched = False
        reason: str | None = None
        for o in (o for o in self.overrides if o.canteen_id == owner and o.day == day):
            touched = True
            reason = o.reason or reason
            if o.period is None and o.is_cancelled:
                patched.clear()
            elif o.is_cancelled and o.period is not None:
                patched.pop(o.period, None)
            elif o.period is not None and o.starts is not None and o.ends is not None:
                patched[o.period] = (o.starts, o.ends)
        return patched, touched, reason

    def plan_for(self, day: date) -> DayPlan:
        weekday = day.weekday()
        overridden = False
        reason: str | None = None
        if self.canteen_id is not None and self._owner_has_weekly(self.canteen_id):
            slots = self._weekly_for(self.canteen_id, weekday)
        else:
            slots, overridden, reason = self._patch(self._weekly_for(None, weekday), None, day)
        if self.canteen_id is not None:
            slots, touched, canteen_reason = self._patch(slots, self.canteen_id, day)
            overridden = overridden or touched
            reason = canteen_reason or reason
        return DayPlan(slots=slots, overridden=overridden, reason=reason)

    def windows_for(self, day: date) -> list[Window]:
        plan = self.plan_for(day)
        return [
            Window(period=p, starts=at_local(day, plan.slots[p][0]), ends=at_local(day, plan.slots[p][1]))
            for p in PERIOD_ORDER
            if p in plan.slots
        ]

    def regular_pattern(self) -> tuple[tuple[str, time, time], ...]:
        if self._regular is None:
            owner = self.canteen_id if self.canteen_id and self._owner_has_weekly(self.canteen_id) else None
            patterns = [
                tuple(sorted((p, s, e) for p, (s, e) in self._weekly_for(owner, wd).items())) for wd in range(7)
            ]
            non_empty = [p for p in patterns if p]
            self._regular = Counter(non_empty).most_common(1)[0][0] if non_empty else ()
        return self._regular


def _special_note(plan: DayPlan) -> str:
    if plan.reason:
        return plan.reason
    periods = [p for p in PERIOD_ORDER if p in plan.slots]
    if len(periods) == 1:
        start, end = plan.slots[periods[0]]
        return f"special hours — {periods[0]} only, {time_range(start, end)}"
    return "special hours"


def week_info(book: ScheduleBook, today: date) -> list[WeekDayInfo]:
    regular = book.regular_pattern()
    days: list[WeekDayInfo] = []
    monday = monday_of(today)
    for offset in range(7):
        day = monday + timedelta(days=offset)
        plan = book.plan_for(day)
        pattern = tuple(sorted((p, s, e) for p, (s, e) in plan.slots.items()))
        if not plan.slots:
            kind: Literal["regular", "special", "closed"] = "closed"
            note: str | None = plan.reason or "canteens closed"
        elif plan.overridden or pattern != regular:
            kind, note = "special", _special_note(plan)
        else:
            kind, note = "regular", None
        days.append(WeekDayInfo(day=day, kind=kind, note=note, is_today=day == today))
    return days


def meal_status(now: datetime, book: ScheduleBook) -> MealState:
    today = local_date(now)
    upcoming: list[Window] = []
    for offset in range(LOOKAHEAD_DAYS):
        upcoming.extend(book.windows_for(today + timedelta(days=offset)))
    index = next((i for i, w in enumerate(upcoming) if w.ends > now), None)
    first = upcoming[index] if index is not None else None
    active = first is not None and first.starts <= now
    following = upcoming[index + 1] if index is not None and index + 1 < len(upcoming) else None
    return MealState(
        state="none" if first is None else "active" if active else "upcoming",
        current=first if active else None,
        next=following if active else first,
        today=book.windows_for(today),
        week=week_info(book, today),
    )


def weekday_short(day: date) -> str:
    return WEEKDAY_SHORT[day.weekday()]
