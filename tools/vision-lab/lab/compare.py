from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mark:
    t: float
    zone: str
    count: int


@dataclass(frozen=True)
class Sample:
    t: float
    ours: dict[str, float]


@dataclass(frozen=True)
class Point:
    t: float
    ours: float
    yours: int


@dataclass
class ZoneResult:
    zone: str
    points: list[Point] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.points)

    @property
    def mae(self) -> float | None:
        return sum(abs(p.ours - p.yours) for p in self.points) / self.n if self.n else None

    @property
    def bias(self) -> float | None:
        return sum(p.ours - p.yours for p in self.points) / self.n if self.n else None

    @property
    def within_one(self) -> float | None:
        return sum(1 for p in self.points if abs(p.ours - p.yours) <= 1) / self.n if self.n else None

    @property
    def exact(self) -> float | None:
        return sum(1 for p in self.points if round(p.ours) == p.yours) / self.n if self.n else None

    def summary(self) -> dict[str, object]:
        return {
            "zone": self.zone,
            "samples": self.n,
            "mae": self.mae,
            "bias": self.bias,
            "within_one": self.within_one,
            "exact": self.exact,
            "points": [[p.t, p.ours, p.yours] for p in self.points],
        }


def truth_at(marks: Sequence[Mark], zone: str, t: float) -> int | None:
    latest = None
    for mark in marks:
        if mark.zone == zone and mark.t <= t and (latest is None or mark.t >= latest.t):
            latest = mark
    return latest.count if latest else None


def compare(
    samples: Iterable[Sample], marks: Sequence[Mark], zones: Iterable[str], skip_s: float = 0.0
) -> list[ZoneResult]:
    results = {zone: ZoneResult(zone) for zone in zones}
    starts = {zone: min((m.t for m in marks if m.zone == zone), default=None) for zone in results}
    for sample in samples:
        for zone, result in results.items():
            start = starts[zone]
            if start is None or sample.t < start + skip_s or zone not in sample.ours:
                continue
            truth = truth_at(marks, zone, sample.t)
            if truth is not None:
                result.points.append(Point(sample.t, sample.ours[zone], truth))
    return list(results.values())


def csv_rows(samples: Iterable[Sample], marks: Sequence[Mark], zones: Sequence[str]) -> list[list[object]]:
    rows: list[list[object]] = [["t_s", "zone", "ours", "yours"]]
    for sample in samples:
        for zone in zones:
            if zone in sample.ours:
                truth = truth_at(marks, zone, sample.t)
                rows.append([round(sample.t, 1), zone, sample.ours[zone], "" if truth is None else truth])
    return rows
