from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import sqrt
from statistics import median
from typing import Any, Literal, Protocol

import numpy as np

from vision.counting import Detection
from vision.geometry import contains

Area = Literal["counter", "kitchen", "floor"]
Method = Literal["face", "badge"]
Point = tuple[float, float]

AREAS: tuple[Area, ...] = ("counter", "kitchen", "floor")


@dataclass(frozen=True)
class WorkArea:
    area: Area
    points: list[Point]


@dataclass(frozen=True)
class StaffMember:
    staff_id: str
    display_name: str
    method: Method
    badge_code: int | None = None
    template: tuple[float, ...] | None = None


@dataclass(frozen=True)
class Evidence:
    track_id: int
    embedding: tuple[float, ...] | None = None
    badge_code: int | None = None


@dataclass(frozen=True)
class StaffSettings:
    face_threshold: float = 0.6
    confirm_matches: int = 3
    release_misses: int = 5
    lost_after_s: float = 3.0
    min_dwell_s: float = 10.0
    absence_s: float = 30.0
    queue_window_s: float = 15.0
    min_confidence: float = 0.25


@dataclass(frozen=True)
class WorkerView:
    detection: Detection
    area: Area


class IdentityReader(Protocol):
    def read(self, image: np.ndarray, people: Sequence[WorkerView]) -> list[Evidence]: ...


def foot_point(d: Detection, width: float, height: float) -> Point:
    return (d.x1 + d.x2) / 2 / width, d.y2 / height


def area_of(work: Sequence[WorkArea], x: float, y: float) -> Area | None:
    return next((w.area for w in work if contains(w.points, x, y)), None)


def _unit(vector: Sequence[float]) -> tuple[float, ...] | None:
    length = sqrt(sum(v * v for v in vector))
    return tuple(v / length for v in vector) if length > 0 else None


def similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return -1.0
    ua, ub = _unit(a), _unit(b)
    if ua is None or ub is None:
        return -1.0
    return sum(x * y for x, y in zip(ua, ub, strict=True))


@dataclass
class TrackIdentity:
    last_seen: float
    candidate: str | None = None
    streak: int = 0
    misses: int = 0
    staff_id: str | None = None


@dataclass
class StaffMatcher:
    staff: list[StaffMember]
    settings: StaffSettings
    tracks: dict[int, TrackIdentity] = field(default_factory=dict)

    def reconfigure(self, staff: list[StaffMember], settings: StaffSettings) -> None:
        kept = {s.staff_id for s in staff}
        self.staff, self.settings = staff, settings
        for track in self.tracks.values():
            if track.staff_id not in kept:
                track.staff_id = None
            if track.candidate not in kept:
                track.candidate, track.streak = None, 0

    def workers(
        self, people: Sequence[Detection], work: Sequence[WorkArea], width: float, height: float
    ) -> list[WorkerView]:
        views = []
        for d in people:
            if d.track_id is None or d.confidence < self.settings.min_confidence:
                continue
            area = area_of(work, *foot_point(d, width, height))
            if area is not None:
                views.append(WorkerView(d, area))
        return views

    def match(self, evidence: Evidence) -> str | None:
        if evidence.badge_code is not None:
            return next(
                (s.staff_id for s in self.staff if s.method == "badge" and s.badge_code == evidence.badge_code), None
            )
        if evidence.embedding is None:
            return None
        scored = [
            (similarity(evidence.embedding, s.template), s.staff_id)
            for s in self.staff
            if s.method == "face" and s.template is not None
        ]
        best = max(scored, default=(-1.0, None))
        return best[1] if best[0] >= self.settings.face_threshold else None

    def _observe(self, track: TrackIdentity, staff_id: str | None) -> None:
        if staff_id is None:
            track.candidate, track.streak = None, 0
            track.misses += 1
            if track.misses >= self.settings.release_misses:
                track.staff_id = None
            return
        track.misses = 0
        if staff_id == track.candidate:
            track.streak += 1
        else:
            track.candidate, track.streak = staff_id, 1
        if track.streak >= self.settings.confirm_matches and track.staff_id != staff_id:
            track.staff_id = staff_id
            for other in self.tracks.values():
                if other is not track and other.staff_id == staff_id:
                    other.staff_id = None

    def update(
        self, workers: Sequence[WorkerView], evidence: Sequence[Evidence], seen: set[int], now: float
    ) -> dict[int, tuple[str, Area]]:
        inside = {v.detection.track_id: v.area for v in workers if v.detection.track_id is not None}
        for track_id, track in list(self.tracks.items()):
            left_work = track_id in seen and track_id not in inside
            lost = track_id not in seen and now - track.last_seen > self.settings.lost_after_s
            if left_work or lost:
                self.tracks.pop(track_id)
        for track_id in inside:
            self.tracks.setdefault(track_id, TrackIdentity(last_seen=now)).last_seen = now
        for item in evidence:
            if item.track_id in inside:
                self._observe(self.tracks[item.track_id], self.match(item))
        return {
            track_id: (track.staff_id, area)
            for track_id, area in inside.items()
            if (track := self.tracks[track_id]).staff_id is not None
        }


@dataclass
class Interval:
    staff_id: str
    area: Area
    first_seen: float
    last_seen: float
    opened: bool = False


@dataclass
class PresenceTracker:
    settings: StaffSettings
    current: dict[tuple[str, Area], Interval] = field(default_factory=dict)
    closed: list[Interval] = field(default_factory=list)

    def update(self, present: Sequence[tuple[str, Area]], now: float) -> None:
        for key in set(present):
            interval = self.current.get(key)
            if interval is None:
                interval = self.current[key] = Interval(key[0], key[1], now, now)
            interval.last_seen = now
            if now - interval.first_seen >= self.settings.min_dwell_s:
                interval.opened = True
        for key, interval in list(self.current.items()):
            if now - interval.last_seen <= self.settings.absence_s:
                continue
            self.current.pop(key)
            if interval.opened:
                self.closed.append(interval)

    def open_intervals(self) -> list[Interval]:
        return [i for i in self.current.values() if i.opened]

    def drain(self) -> list[dict[str, Any]]:
        rows = [
            {"staff_id": i.staff_id, "area": i.area, "started_at": i.first_seen, "ended_at": i.last_seen}
            for i in self.closed
        ] + [
            {"staff_id": i.staff_id, "area": i.area, "started_at": i.first_seen, "ended_at": None}
            for i in self.open_intervals()
        ]
        self.closed = []
        return rows


@dataclass
class QueueCounter:
    areas: list[list[Point]]
    settings: StaffSettings
    samples: deque[tuple[float, int]] = field(default_factory=deque)

    def count(self, people: Sequence[Detection], width: float, height: float, skip: set[int] | None = None) -> int:
        return sum(
            1
            for d in people
            if d.confidence >= self.settings.min_confidence
            and (d.track_id is None or d.track_id not in (skip or set()))
            and any(contains(area, *foot_point(d, width, height)) for area in self.areas)
        )

    def update(self, people: Sequence[Detection], width: float, height: float, now: float, skip: set[int]) -> int:
        people_now = self.count(people, width, height, skip)
        self.samples.append((now, people_now))
        while self.samples and now - self.samples[0][0] > self.settings.queue_window_s:
            self.samples.popleft()
        return people_now

    def reading(self) -> dict[str, int] | None:
        if not self.areas or not self.samples:
            return None
        return {"people": round(median(n for _, n in self.samples))}


def to_iso(at: float, epoch_offset: float) -> str:
    return datetime.fromtimestamp(at + epoch_offset, UTC).isoformat()


def presence_payload(rows: list[dict[str, Any]], epoch_offset: float) -> list[dict[str, Any]]:
    return [
        {
            **row,
            "started_at": to_iso(row["started_at"], epoch_offset),
            "ended_at": None if row["ended_at"] is None else to_iso(row["ended_at"], epoch_offset),
        }
        for row in rows
    ]


def _points(raw: Sequence[Sequence[float]]) -> list[Point]:
    return [(float(p[0]), float(p[1])) for p in raw]


def work_areas_from_config(config: dict[str, Any]) -> list[WorkArea]:
    raw = [*config.get("work", []), *(a for a in config.get("ignore", []) if a.get("type") == "work")]
    return [WorkArea(a["area"], _points(a["points"])) for a in raw if a.get("area") in AREAS]


def queue_areas_from_config(config: dict[str, Any]) -> list[list[Point]]:
    return [_points(a["points"]) for a in config.get("ignore", []) if a.get("type") == "queue"]


def staff_settings_from_config(config: dict[str, Any]) -> StaffSettings:
    s = config.get("settings", {})
    defaults = StaffSettings()
    return StaffSettings(
        face_threshold=float(s.get("face_threshold", defaults.face_threshold)),
        confirm_matches=int(s.get("confirm_matches", defaults.confirm_matches)),
        release_misses=int(s.get("release_misses", defaults.release_misses)),
        lost_after_s=float(s.get("lost_after_s", defaults.lost_after_s)),
        min_dwell_s=float(s.get("staff_dwell_s", defaults.min_dwell_s)),
        absence_s=float(s.get("staff_absence_s", defaults.absence_s)),
        queue_window_s=float(s.get("queue_window_s", defaults.queue_window_s)),
        min_confidence=float(s.get("min_confidence", defaults.min_confidence)),
    )


def staff_from_response(payload: dict[str, Any] | list[dict[str, Any]]) -> list[StaffMember]:
    rows = payload.get("staff", []) if isinstance(payload, dict) else payload
    result = []
    for row in rows:
        method = row.get("method")
        badge = row.get("badge_code")
        template = row.get("template")
        if method == "badge" and badge is not None:
            result.append(StaffMember(str(row["staff_id"]), str(row["display_name"]), "badge", int(badge)))
        elif method == "face" and template:
            vector = tuple(float(v) for v in template)
            result.append(StaffMember(str(row["staff_id"]), str(row["display_name"]), "face", None, vector))
    return result
