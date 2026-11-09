from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from math import hypot
from typing import Any

AREAS = ("counter", "kitchen", "floor")
MAX_STEP_S = 2.0


@dataclass
class Worker:
    label: str
    first: float
    last: float
    x: float
    y: float
    area: str
    name: str | None = None
    seconds: dict[str, float] = field(default_factory=lambda: dict.fromkeys(AREAS, 0.0))

    @property
    def shown(self) -> str:
        return self.name or self.label

    def summary(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "name": self.name,
            "first": round(self.first, 1),
            "last": round(self.last, 1),
            "seconds": {k: round(v, 1) for k, v in self.seconds.items()},
            "total": round(sum(self.seconds.values()), 1),
        }


@dataclass
class Coverage:
    min_gap_s: float = 30.0
    open_s: float = 0.0
    staffed_s: float = 0.0
    gaps: list[tuple[float, float]] = field(default_factory=list)
    gap_start: float | None = None

    def update(self, staffed: bool, t: float, dt: float) -> None:
        self.open_s += dt
        if staffed:
            self.staffed_s += dt
            self._close(t)
        elif self.gap_start is None:
            self.gap_start = t

    def _close(self, t: float) -> None:
        if self.gap_start is not None and t - self.gap_start >= self.min_gap_s:
            self.gaps.append((self.gap_start, t))
        self.gap_start = None

    def finish(self, t: float) -> None:
        self._close(t)

    def summary(self, t: float) -> dict[str, Any]:
        gaps = list(self.gaps)
        if self.gap_start is not None and t - self.gap_start >= self.min_gap_s:
            gaps.append((self.gap_start, t))
        return {
            "open_s": round(self.open_s, 1),
            "staffed_s": round(self.staffed_s, 1),
            "share": self.staffed_s / self.open_s if self.open_s > 0 else None,
            "gaps": [[round(a, 1), round(b, 1)] for a, b in gaps],
            "min_gap_s": self.min_gap_s,
        }


@dataclass
class WorkerBook:
    rejoin_s: float = 15.0
    rejoin_distance: float = 0.1
    coverage: Coverage = field(default_factory=Coverage)
    tracks: dict[int, Worker] = field(default_factory=dict)
    lost: dict[int, Worker] = field(default_factory=dict)
    everyone: list[Worker] = field(default_factory=list)
    last_t: float | None = None
    numbered: int = 0

    def _rejoin(self, track: int, x: float, y: float) -> Worker | None:
        if track in self.lost:
            return self.lost.pop(track)
        near = [(hypot(w.x - x, w.y - y), key) for key, w in self.lost.items()]
        near = [n for n in near if n[0] <= self.rejoin_distance]
        return self.lost.pop(min(near)[1]) if near else None

    def update(
        self, views: Iterable[tuple[int, str, float, float]], named: dict[int, str], t: float, has_counter: bool
    ) -> None:
        dt = 0.0 if self.last_t is None else min(MAX_STEP_S, max(0.0, t - self.last_t))
        self.last_t = t
        self.lost = {k: w for k, w in self.lost.items() if t - w.last <= self.rejoin_s}
        seen: set[int] = set()
        staffed = False
        for track, area, x, y in views:
            worker = self.tracks.get(track) or self._rejoin(track, x, y)
            if worker is None:
                self.numbered += 1
                worker = Worker(f"Worker {self.numbered}", t, t, x, y, area)
                self.everyone.append(worker)
            worker.seconds[area] = worker.seconds.get(area, 0.0) + dt
            worker.last, worker.x, worker.y, worker.area = t, x, y, area
            self.tracks[track] = worker
            seen.add(track)
            staffed = staffed or area == "counter"
        for track in [k for k in self.tracks if k not in seen]:
            self.lost[track] = self.tracks.pop(track)
        for track, name in named.items():
            if name and track in self.tracks:
                self.assign(track, name)
        if has_counter:
            self.coverage.update(staffed, t, dt)

    def named_on_screen(self, besides: int | None = None) -> set[str]:
        return {w.name for k, w in self.tracks.items() if w.name and k != besides}

    def worker_on(self, label: str) -> int | None:
        return next((k for k, w in self.tracks.items() if w.label == label), None)

    def assign(self, track: int, name: str) -> bool:
        current = self.tracks.get(track)
        if current is None or current.name == name:
            return False
        if current.name is not None:
            return False
        target = next((w for w in self.everyone if w.name == name), None)
        if target is None:
            current.name = name
            return True
        if any(w is target for k, w in self.tracks.items() if k != track):
            return False
        for area, seconds in current.seconds.items():
            target.seconds[area] = target.seconds.get(area, 0.0) + seconds
        target.first, target.last = min(target.first, current.first), max(target.last, current.last)
        target.x, target.y, target.area = current.x, current.y, current.area
        self.tracks[track] = target
        self.lost = {k: w for k, w in self.lost.items() if w is not target and w is not current}
        self.everyone = [w for w in self.everyone if w is not current]
        return True

    def labels(self) -> dict[int, str]:
        return {
            track: f"{w.shown} · {w.area} · {int(sum(w.seconds.values()) // 60)} min"
            for track, w in self.tracks.items()
        }

    def summary(self, t: float, min_seconds: float = 3.0) -> dict[str, Any]:
        kept = [w for w in self.everyone if sum(w.seconds.values()) >= min_seconds]
        return {
            "workers": [w.summary() for w in kept],
            "brief": len(self.everyone) - len(kept),
            "coverage": self.coverage.summary(t),
        }


@dataclass
class Enrolment:
    name: str
    track: int
    started: float
    needed: int = 5
    timeout_s: float = 20.0
    agree: float = 0.45
    samples: list[Sequence[float]] = field(default_factory=list)

    def add(self, embedding: Sequence[float]) -> None:
        self.samples.append(tuple(embedding))

    def done(self, t: float) -> bool:
        return len(self.samples) >= self.needed or t - self.started > self.timeout_s

    def template(self) -> list[float] | None:
        from vision.identity import average_template, samples_agree

        if len(self.samples) < 2 or not samples_agree(self.samples, self.agree):
            return None
        return average_template(self.samples)
