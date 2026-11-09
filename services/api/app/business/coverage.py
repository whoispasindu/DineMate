from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_GAP = timedelta(minutes=2)
QUEUE_HOLD = timedelta(seconds=60)
QUEUE_LIMIT = 5


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


@dataclass(frozen=True)
class Coverage:
    open_min: float
    covered_min: float
    gaps: list[Interval]

    @property
    def share(self) -> float | None:
        return self.covered_min / self.open_min if self.open_min > 0 else None


@dataclass(frozen=True)
class QueuePoint:
    at: datetime
    people: int


@dataclass(frozen=True)
class QueueAlert:
    start: datetime
    end: datetime
    peak: int


def merge(intervals: Iterable[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for item in sorted((i for i in intervals if i.end > i.start), key=lambda i: i.start):
        if merged and item.start <= merged[-1].end:
            last = merged[-1]
            merged[-1] = Interval(last.start, max(last.end, item.end))
        else:
            merged.append(item)
    return merged


def clip(intervals: Iterable[Interval], window: Interval) -> list[Interval]:
    return [
        Interval(max(i.start, window.start), min(i.end, window.end))
        for i in intervals
        if i.end > window.start and i.start < window.end
    ]


def coverage(presence: Iterable[Interval], open_windows: Sequence[Interval], min_gap: timedelta = MIN_GAP) -> Coverage:
    covered = 0.0
    total = 0.0
    gaps: list[Interval] = []
    staffed = merge(presence)
    for window in open_windows:
        if window.end <= window.start:
            continue
        total += window.minutes
        inside = merge(clip(staffed, window))
        covered += sum(i.minutes for i in inside)
        cursor = window.start
        for part in [*inside, Interval(window.end, window.end)]:
            if part.start - cursor >= min_gap:
                gaps.append(Interval(cursor, part.start))
            cursor = max(cursor, part.end)
    return Coverage(open_min=total, covered_min=covered, gaps=gaps)


def queue_alerts(
    points: Sequence[QueuePoint], limit: int = QUEUE_LIMIT, hold: timedelta = QUEUE_HOLD
) -> list[QueueAlert]:
    alerts: list[QueueAlert] = []
    start: datetime | None = None
    last: datetime | None = None
    peak = 0
    for point in sorted(points, key=lambda p: p.at):
        if point.people > limit:
            if start is None:
                start, peak = point.at, point.people
            peak = max(peak, point.people)
            last = point.at
            continue
        if start is not None and last is not None and last - start >= hold:
            alerts.append(QueueAlert(start, point.at, peak))
        start, last, peak = None, None, 0
    if start is not None and last is not None and last - start >= hold:
        alerts.append(QueueAlert(start, last, peak))
    return alerts
