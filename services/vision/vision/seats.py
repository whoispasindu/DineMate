from dataclasses import dataclass, field
from math import hypot
from typing import Any, Literal

from vision.counting import Detection, Zone
from vision.geometry import contains
from vision.posture import Posture, PostureSettings, classify, hip_point

SeatState = Literal["free", "occupied", "held", "unknown"]

BELONGINGS = frozenset({"backpack", "handbag", "suitcase", "laptop", "book"})
TABLEWARE = frozenset(
    {"cup", "bowl", "bottle", "wine glass", "fork", "knife", "spoon", "sandwich", "pizza", "cake", "donut", "hot dog"}
)
OBJECT_REACH = 1.3
CROWD_UNKNOWN_RATIO = 0.4


@dataclass(frozen=True)
class Seat:
    seat_id: str
    zone_id: str
    x: float
    y: float


@dataclass(frozen=True)
class SeatSettings:
    dwell_s: float = 20.0
    return_s: float = 3.0
    clear_s: float = 30.0
    held_after_s: float = 20.0
    hidden_free_s: float = 10.0
    hidden_hold_s: float = 120.0
    abandoned_s: float = 300.0
    gap_s: float = 3.0
    seat_radius: float = 0.06
    min_confidence: float = 0.25
    posture: PostureSettings = field(default_factory=PostureSettings)


@dataclass(frozen=True)
class ObjectDetection:
    label: str
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


@dataclass(frozen=True)
class SeatObservation:
    person: bool = False
    belongings: int = 0
    tableware: int = 0
    hidden: bool = False


@dataclass
class SeatTrack:
    state: SeatState = "unknown"
    since: float = 0.0
    person_since: float | None = None
    person_last: float | None = None
    belongings_since: float | None = None
    tableware_since: float | None = None
    empty_since: float | None = None
    hidden_since: float | None = None

    @property
    def free_soon(self) -> bool:
        return self.state == "occupied" and self.person_since is None and self.tableware_since is not None


@dataclass(frozen=True)
class PersonView:
    detection: Detection
    posture: Posture
    seat_id: str | None
    zone_id: str | None


def _set(current: float | None, active: bool, now: float) -> float | None:
    if not active:
        return None
    return now if current is None else current


def step(track: SeatTrack, obs: SeatObservation, now: float, settings: SeatSettings) -> SeatTrack:
    if obs.person:
        track.person_last = now
        track.person_since = _set(track.person_since, True, now)
    elif track.person_last is None or now - track.person_last > settings.gap_s:
        track.person_since = None
    present = track.person_since is not None
    track.hidden_since = _set(track.hidden_since, obs.hidden, now)
    if present or obs.hidden:
        track.belongings_since = track.tableware_since = track.empty_since = None
    else:
        track.belongings_since = _set(track.belongings_since, obs.belongings > 0, now)
        track.tableware_since = _set(track.tableware_since, obs.belongings == 0 and obs.tableware > 0, now)
        track.empty_since = _set(track.empty_since, obs.belongings == 0 and obs.tableware == 0, now)
    _transition(track, _next_state(track, now, settings), now)
    return track


def _next_state(track: SeatTrack, now: float, settings: SeatSettings) -> SeatState:
    state = track.state
    if track.person_since is not None:
        needed = settings.return_s if state in ("occupied", "held") else settings.dwell_s
        return "occupied" if now - track.person_since >= needed else state
    if track.hidden_since is not None:
        hidden_for = now - track.hidden_since
        if state == "free" and hidden_for >= settings.hidden_free_s:
            return "unknown"
        if state in ("occupied", "held") and hidden_for >= settings.hidden_hold_s:
            return "unknown"
        return state
    if track.belongings_since is not None:
        wait = 0.0 if state in ("occupied", "held") else settings.held_after_s
        return "held" if now - track.belongings_since >= wait else state
    if track.tableware_since is not None:
        if state in ("occupied", "held"):
            return "free" if now - track.tableware_since >= settings.abandoned_s else state
        return "free" if now - track.tableware_since >= settings.clear_s else state
    if track.empty_since is not None and now - track.empty_since >= settings.clear_s:
        return "free"
    return state


def _transition(track: SeatTrack, state: SeatState, now: float) -> None:
    if state != track.state:
        track.state = state
        track.since = now


def zone_reading(zone: Zone, counts: dict[str, int]) -> dict[str, Any]:
    occupied = counts["occupied"] + counts["held"]
    unknown = counts["unknown"]
    seats = max(sum(counts[s] for s in ("free", "occupied", "held", "unknown")), 1)
    ratio = unknown / seats
    confidence = "high" if unknown == 0 else "medium" if ratio <= 0.2 else "low"
    return {
        "zone_id": zone.zone_id,
        "estimated_occupied": min(occupied + unknown, zone.capacity),
        "occupied_low": min(occupied, zone.capacity),
        "occupied_high": min(occupied + unknown, zone.capacity),
        "confidence": confidence,
        "samples": 1,
    }


@dataclass
class SeatTracker:
    zones: list[Zone]
    seats: list[Seat]
    ignore: list[list[tuple[float, float]]]
    settings: SeatSettings
    tracks: dict[str, SeatTrack] = field(default_factory=dict)
    standing: dict[str, int] = field(default_factory=dict)

    def reconfigure(
        self, zones: list[Zone], seats: list[Seat], ignore: list[list[tuple[float, float]]], settings: SeatSettings
    ) -> None:
        kept = {s.seat_id for s in seats}
        self.zones, self.seats, self.ignore, self.settings = zones, seats, ignore, settings
        self.tracks = {k: v for k, v in self.tracks.items() if k in kept}

    def _zone_of(self, x: float, y: float) -> str | None:
        if any(contains(area, x, y) for area in self.ignore):
            return None
        return next((z.zone_id for z in self.zones if contains(z.points, x, y)), None)

    def update(
        self,
        people: list[Detection],
        objects: list[ObjectDetection],
        width: float,
        height: float,
        now: float,
    ) -> list[PersonView]:
        radius = self.settings.seat_radius * width
        seat_px = {s.seat_id: (s.x * width, s.y * height) for s in self.seats}
        candidates: list[tuple[float, int, str]] = []
        views: list[PersonView] = []
        postures: list[Posture] = []
        for index, person in enumerate(people):
            box = (person.x1, person.y1, person.x2, person.y2)
            hx, hy = hip_point(box, person.keypoints)
            nearest = min(
                ((hypot(hx - sx, hy - sy), sid) for sid, (sx, sy) in seat_px.items()), default=(float("inf"), "")
            )
            seat_y = seat_px[nearest[1]][1] if nearest[0] <= radius else None
            posture = classify(box, person.keypoints, height, self.settings.posture, seat_y)
            postures.append(posture)
            if person.confidence < self.settings.min_confidence or posture == "standing":
                continue
            for sid, (sx, sy) in seat_px.items():
                distance = hypot(hx - sx, hy - sy)
                if distance <= radius:
                    candidates.append((distance, index, sid))
        assigned: dict[int, str] = {}
        taken: set[str] = set()
        for _distance, index, sid in sorted(candidates):
            if index not in assigned and sid not in taken:
                assigned[index] = sid
                taken.add(sid)
        blockers = [
            p for i, p in enumerate(people) if i not in assigned and p.confidence >= self.settings.min_confidence
        ]
        belongings = {s.seat_id: 0 for s in self.seats}
        tableware = {s.seat_id: 0 for s in self.seats}
        for obj in objects:
            if obj.confidence < self.settings.min_confidence:
                continue
            ox, oy = (obj.x1 + obj.x2) / 2, (obj.y1 + obj.y2) / 2
            nearest = min(
                ((hypot(ox - sx, oy - sy), sid) for sid, (sx, sy) in seat_px.items()), default=(float("inf"), "")
            )
            if nearest[0] > radius * OBJECT_REACH:
                continue
            if obj.label in BELONGINGS:
                belongings[nearest[1]] += 1
            elif obj.label in TABLEWARE:
                tableware[nearest[1]] += 1
        for seat in self.seats:
            sx, sy = seat_px[seat.seat_id]
            hidden = any(b.x1 <= sx <= b.x2 and b.y1 <= sy <= b.y2 for b in blockers)
            obs = SeatObservation(
                person=seat.seat_id in taken,
                belongings=belongings[seat.seat_id],
                tableware=tableware[seat.seat_id],
                hidden=hidden and seat.seat_id not in taken,
            )
            track = self.tracks.setdefault(seat.seat_id, SeatTrack(since=now))
            step(track, obs, now, self.settings)
        self.standing = {z.zone_id: 0 for z in self.zones}
        for index, person in enumerate(people):
            hx, hy = hip_point((person.x1, person.y1, person.x2, person.y2), person.keypoints)
            zone_id = self._zone_of(hx / width, hy / height)
            if postures[index] == "standing" and zone_id is not None:
                self.standing[zone_id] += 1
            seat_id = assigned.get(index)
            views.append(PersonView(person, postures[index], seat_id, zone_id))
        return views

    def counts(self, zone_id: str) -> dict[str, int]:
        result = {"free": 0, "occupied": 0, "held": 0, "unknown": 0, "free_soon": 0}
        for seat in self.seats:
            if seat.zone_id != zone_id:
                continue
            track = self.tracks.get(seat.seat_id)
            state = track.state if track else "unknown"
            result[state] += 1
            if track and track.free_soon:
                result["free_soon"] += 1
        return result

    def crowded(self, zone_id: str) -> bool:
        counts = self.counts(zone_id)
        seats = sum(counts[s] for s in ("free", "occupied", "held", "unknown"))
        if seats == 0:
            return False
        standing = self.standing.get(zone_id, 0)
        return counts["unknown"] / seats >= CROWD_UNKNOWN_RATIO or standing >= max(4, seats // 2)

    def readings(self) -> list[dict[str, Any]]:
        zones_with_seats = {s.zone_id for s in self.seats}
        return [zone_reading(z, self.counts(z.zone_id)) for z in self.zones if z.zone_id in zones_with_seats]

    def snapshot(self, now: float) -> dict[str, Any]:
        zones_with_seats = {s.zone_id for s in self.seats}
        return {
            "zones": [
                {
                    "zone_id": z.zone_id,
                    **self.counts(z.zone_id),
                    "standing": self.standing.get(z.zone_id, 0),
                    "crowded": self.crowded(z.zone_id),
                }
                for z in self.zones
                if z.zone_id in zones_with_seats
            ],
            "seats": [
                {
                    "seat_id": s.seat_id,
                    "zone_id": s.zone_id,
                    "state": track.state,
                    "for_s": round(now - track.since, 1),
                    "free_soon": track.free_soon,
                }
                for s in self.seats
                if (track := self.tracks.get(s.seat_id)) is not None
            ],
        }


def seats_from_config(config: dict[str, Any]) -> list[Seat]:
    return [
        Seat(str(seat["seat_id"]), str(zone["zone_id"]), float(seat["x"]), float(seat["y"]))
        for zone in config.get("zones", [])
        for seat in zone.get("seats", [])
    ]


def seat_settings_from_config(config: dict[str, Any]) -> SeatSettings:
    s = config.get("settings", {})
    defaults = SeatSettings()
    return SeatSettings(
        dwell_s=float(s.get("dwell_s", defaults.dwell_s)),
        clear_s=float(s.get("clear_s", defaults.clear_s)),
        held_after_s=float(s.get("held_after_s", defaults.held_after_s)),
        hidden_free_s=float(s.get("hidden_free_s", defaults.hidden_free_s)),
        hidden_hold_s=float(s.get("hidden_hold_s", defaults.hidden_hold_s)),
        abandoned_s=float(s.get("abandoned_s", defaults.abandoned_s)),
        seat_radius=float(s.get("seat_radius", defaults.seat_radius)),
        min_confidence=float(s.get("min_confidence", defaults.min_confidence)),
        posture=PostureSettings(
            seated_ratio=float(s.get("seated_ratio", 0.7)),
            h_stand_a=s.get("h_stand_a"),
            h_stand_b=s.get("h_stand_b"),
        ),
    )
