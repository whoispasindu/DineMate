from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from vision.counting import Assignment, Detection, ZoneCounter, zones_from_config
from vision.seats import ObjectDetection, Seat, SeatTracker, seat_settings_from_config, seats_from_config

OBJECTS_EVERY_S = 5.0


class PeopleDetector(Protocol):
    imgsz: int | None

    def detect(self, image: np.ndarray) -> list[Detection]: ...


class ThingsDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[ObjectDetection]: ...


@dataclass(frozen=True)
class Models:
    detect: str
    pose: str
    imgsz: int | None = None


class Pipeline:
    def __init__(
        self,
        config: dict[str, Any],
        models: Models,
        people: PeopleDetector | None = None,
        objects: ThingsDetector | None = None,
    ) -> None:
        self.models = models
        self.fixed_people = people
        self.fixed_objects = objects
        self.people: PeopleDetector | None = people
        self.objects: ThingsDetector | None = objects
        self.uses_pose = False
        self.objects_at: float | None = None
        self.last_objects: list[ObjectDetection] = []
        self.counter = ZoneCounter([], [], zones_from_config({})[2])
        self.tracker = SeatTracker([], [], [], seat_settings_from_config({}))
        self.configure(config)

    @property
    def seat_mode(self) -> bool:
        return bool(self.tracker.seats)

    @property
    def imgsz(self) -> int | None:
        return self.people.imgsz if self.people else None

    def configure(self, config: dict[str, Any]) -> None:
        zones, ignore, settings = zones_from_config(config)
        seats = seats_from_config(config)
        seat_zones = {s.zone_id for s in seats}
        self.settings = config.get("settings", {})
        self.counter.reconfigure([z for z in zones if z.zone_id not in seat_zones], ignore, settings)
        self.tracker.reconfigure(
            [z for z in zones if z.zone_id in seat_zones], seats, ignore, seat_settings_from_config(config)
        )
        self._load_detectors()

    def _load_detectors(self) -> None:
        from vision.detector import ObjectDetector, YoloDetector

        confidence = float(self.settings.get("min_confidence", 0.25))
        if self.fixed_people is None and (self.people is None or self.uses_pose != self.seat_mode):
            path = self.models.pose if self.seat_mode else self.models.detect
            self.people = YoloDetector(path, imgsz=self.models.imgsz, confidence=confidence)
            self.uses_pose = self.seat_mode
        if self.fixed_objects is None and self.seat_mode and self.objects is None:
            self.objects = ObjectDetector(self.models.detect, imgsz=self.models.imgsz, confidence=confidence)

    def process(self, image: np.ndarray, at: float) -> list[Assignment]:
        if self.people is None:
            raise RuntimeError("No people detector loaded")
        detections = self.people.detect(image)
        height, width = image.shape[:2]
        assignments = self.counter.update(detections, width, height, at) if self.counter.zones else []
        if not self.seat_mode:
            return assignments
        every = float(self.settings.get("objects_every_s", OBJECTS_EVERY_S))
        if self.objects is not None and (self.objects_at is None or at - self.objects_at >= every):
            self.last_objects = self.objects.detect(image)
            self.objects_at = at
        views = self.tracker.update(detections, self.last_objects, width, height, at)
        for view in views:
            if view.zone_id is None and view.seat_id is None:
                continue
            reason = "seated" if view.seat_id else view.posture
            assignments.append(Assignment(view.detection, view.zone_id, view.seat_id is not None, reason))
        return assignments

    def readings(self) -> list[dict[str, Any]]:
        return self.counter.readings() + self.tracker.readings()

    def snapshot(self, at: float) -> dict[str, Any] | None:
        return self.tracker.snapshot(at) if self.seat_mode else None

    def seat_states(self) -> list[tuple[Seat, str]]:
        return [
            (seat, track.state if (track := self.tracker.tracks.get(seat.seat_id)) else "unknown")
            for seat in self.tracker.seats
        ]

    def labels(self) -> dict[str, str]:
        result = {}
        for zone in self.tracker.zones:
            c = self.tracker.counts(zone.zone_id)
            text = f"{zone.name}: {c['free']} free | {c['occupied']} taken | {c['held']} held"
            if c["unknown"]:
                text += f" | {c['unknown']} hidden"
            if self.tracker.crowded(zone.zone_id):
                text += " (crowded)"
            result[zone.zone_id] = text
        return result

    @property
    def zones(self) -> list[Any]:
        return self.counter.zones + self.tracker.zones

    @property
    def ignore(self) -> list[list[tuple[float, float]]]:
        return self.counter.ignore
