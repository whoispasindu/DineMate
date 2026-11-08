from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Any

from vision.geometry import contains

TORSO_FRACTION = 0.3
FORGET_AFTER_S = 3.0
LOW_CONFIDENCE = 0.4


@dataclass(frozen=True)
class Detection:
    track_id: int | None
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    keypoints: tuple[tuple[float, float, float], ...] | None = None


@dataclass(frozen=True)
class Zone:
    zone_id: str
    name: str
    capacity: int
    points: list[tuple[float, float]]


@dataclass(frozen=True)
class CountSettings:
    dwell_s: float = 20.0
    smoothing_s: float = 60.0
    min_confidence: float = 0.25
    seated_ratio: float = 0.7
    h_stand_a: float | None = None
    h_stand_b: float | None = None


@dataclass(frozen=True)
class ZoneSample:
    at: float
    count: int
    uncertain: int


@dataclass(frozen=True)
class Assignment:
    detection: Detection
    zone_id: str | None
    counted: bool
    reason: str


@dataclass
class ZoneCounter:
    zones: list[Zone]
    ignore: list[list[tuple[float, float]]]
    settings: CountSettings
    first_seen: dict[tuple[str, int], float] = field(default_factory=dict)
    last_seen: dict[tuple[str, int], float] = field(default_factory=dict)
    history: dict[str, deque[ZoneSample]] = field(default_factory=dict)

    def reconfigure(self, zones: list[Zone], ignore: list[list[tuple[float, float]]], settings: CountSettings) -> None:
        kept = {z.zone_id for z in zones}
        self.zones, self.ignore, self.settings = zones, ignore, settings
        self.history = {k: v for k, v in self.history.items() if k in kept}
        self.first_seen = {k: v for k, v in self.first_seen.items() if k[0] in kept}
        self.last_seen = {k: v for k, v in self.last_seen.items() if k[0] in kept}

    def _is_seated(self, d: Detection, anchor_y: float, height: float) -> bool:
        a, b = self.settings.h_stand_a, self.settings.h_stand_b
        if a is None or b is None:
            return True
        expected = a * anchor_y + b
        return expected <= 0 or (d.y2 - d.y1) / height < self.settings.seated_ratio * expected

    def assign(self, detections: list[Detection], width: float, height: float, now: float) -> list[Assignment]:
        result: list[Assignment] = []
        seen: set[tuple[str, int]] = set()
        for d in detections:
            ax = (d.x1 + d.x2) / 2 / width
            ay = (d.y1 + (d.y2 - d.y1) * TORSO_FRACTION) / height
            if d.confidence < self.settings.min_confidence:
                result.append(Assignment(d, None, False, "low confidence"))
                continue
            if any(contains(area, ax, ay) for area in self.ignore):
                result.append(Assignment(d, None, False, "ignored area"))
                continue
            zone = next((z for z in self.zones if contains(z.points, ax, ay)), None)
            if zone is None:
                result.append(Assignment(d, None, False, "outside zones"))
                continue
            if d.track_id is None:
                result.append(Assignment(d, zone.zone_id, False, "not tracked yet"))
                continue
            if not self._is_seated(d, ay, height):
                result.append(Assignment(d, zone.zone_id, False, "standing"))
                continue
            key = (zone.zone_id, d.track_id)
            seen.add(key)
            self.first_seen.setdefault(key, now)
            self.last_seen[key] = now
            dwelled = now - self.first_seen[key] >= self.settings.dwell_s
            result.append(Assignment(d, zone.zone_id, dwelled, "counted" if dwelled else "waiting for dwell"))
        for key in [k for k, t in self.last_seen.items() if k not in seen and now - t > FORGET_AFTER_S]:
            self.first_seen.pop(key, None)
            self.last_seen.pop(key, None)
        return result

    def update(self, detections: list[Detection], width: float, height: float, now: float) -> list[Assignment]:
        assignments = self.assign(detections, width, height, now)
        for zone in self.zones:
            counted = [a for a in assignments if a.zone_id == zone.zone_id and a.counted]
            uncertain = sum(1 for a in counted if a.detection.confidence < LOW_CONFIDENCE)
            samples = self.history.setdefault(zone.zone_id, deque())
            samples.append(ZoneSample(now, min(len(counted), zone.capacity), uncertain))
            while samples and now - samples[0].at > self.settings.smoothing_s:
                samples.popleft()
        return assignments

    def readings(self) -> list[dict[str, Any]]:
        readings = []
        for zone in self.zones:
            samples = self.history.get(zone.zone_id)
            if not samples:
                continue
            counts = [s.count for s in samples]
            estimate = round(median(counts))
            spread = 1 + round(median(s.uncertain for s in samples)) + (1 if max(counts) - min(counts) > 2 else 0)
            confidence = "high" if spread <= 1 else "medium" if spread == 2 else "low"
            readings.append(
                {
                    "zone_id": zone.zone_id,
                    "estimated_occupied": estimate,
                    "occupied_low": max(0, estimate - spread),
                    "occupied_high": min(zone.capacity, estimate + spread),
                    "confidence": confidence,
                    "samples": len(samples),
                }
            )
        return readings


def zones_from_config(config: dict[str, Any]) -> tuple[list[Zone], list[list[tuple[float, float]]], CountSettings]:
    zones = [
        Zone(z["zone_id"], z["name"], int(z["capacity"]), [(float(x), float(y)) for x, y in z["points"]])
        for z in config.get("zones", [])
    ]
    ignore = [[(float(x), float(y)) for x, y in area["points"]] for area in config.get("ignore", [])]
    s = config.get("settings", {})
    settings = CountSettings(
        dwell_s=float(s.get("dwell_s", 20)),
        smoothing_s=float(s.get("smoothing_s", 60)),
        min_confidence=float(s.get("min_confidence", 0.25)),
        seated_ratio=float(s.get("seated_ratio", 0.7)),
        h_stand_a=s.get("h_stand_a"),
        h_stand_b=s.get("h_stand_b"),
    )
    return zones, ignore, settings
