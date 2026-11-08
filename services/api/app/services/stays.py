from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from statistics import median

from app.services.timeutil import CAMPUS_TZ

MIN_STAY_MIN = 1.0
MAX_STAY_MIN = 240.0
HORIZON_MIN = 10.0
UNSEEN_LEAVE_CHANCE = 0.5


def stay_minutes(started_at: datetime, ended_at: datetime) -> float | None:
    minutes = (ended_at - started_at).total_seconds() / 60
    return minutes if MIN_STAY_MIN <= minutes <= MAX_STAY_MIN else None


def median_by_hour(sessions: Iterable[tuple[datetime, datetime]]) -> dict[int, tuple[float, int]]:
    by_hour: dict[int, list[float]] = defaultdict(list)
    for started_at, ended_at in sessions:
        minutes = stay_minutes(started_at, ended_at)
        if minutes is not None:
            by_hour[started_at.astimezone(CAMPUS_TZ).hour].append(minutes)
    return {hour: (round(median(values), 1), len(values)) for hour, values in sorted(by_hour.items())}


def leave_chance(elapsed: float, durations: list[float], horizon: float = HORIZON_MIN) -> float:
    still_there = [d for d in durations if d > elapsed]
    if not still_there:
        return UNSEEN_LEAVE_CHANCE
    leaving = sum(1 for d in still_there if d <= elapsed + horizon)
    return leaving / len(still_there)


def likely_to_free(
    elapsed_minutes: Iterable[float], durations: list[float], horizon: float = HORIZON_MIN
) -> int | None:
    if not durations:
        return None
    return round(sum(leave_chance(e, durations, horizon) for e in elapsed_minutes))
