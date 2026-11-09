from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from vision.counting import Assignment, Detection, ZoneCounter, zones_from_config
from vision.seats import ObjectDetection, Seat, SeatTracker, seat_settings_from_config, seats_from_config
from vision.staff import (
    Area,
    IdentityReader,
    PresenceTracker,
    QueueCounter,
    StaffMatcher,
    StaffMember,
    WorkArea,
    WorkerView,
    presence_payload,
    queue_areas_from_config,
    staff_settings_from_config,
    work_areas_from_config,
)
from vision.stays import StayClock, stay_text

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
        identity: IdentityReader | None = None,
        staff: list[StaffMember] | None = None,
    ) -> None:
        self.models = models
        self.identity = identity
        self.fixed_people = people
        self.fixed_objects = objects
        self.people: PeopleDetector | None = people
        self.objects: ThingsDetector | None = objects
        self.uses_pose = False
        self.objects_at: float | None = None
        self.last_objects: list[ObjectDetection] = []
        self.counter = ZoneCounter([], [], zones_from_config({})[2])
        self.tracker = SeatTracker([], [], [], seat_settings_from_config({}))
        self.work: list[WorkArea] = []
        self.matcher = StaffMatcher(staff or [], staff_settings_from_config({}))
        self.presence = PresenceTracker(self.matcher.settings)
        self.queue = QueueCounter([], self.matcher.settings)
        self.named: dict[int, tuple[str, Area]] = {}
        self.workers_seen: list[WorkerView] = []
        self.people_seen: list[Detection] = []
        self.stays = StayClock()
        self.stay_times: dict[int, float] = {}
        self.configure(config)

    @property
    def seat_mode(self) -> bool:
        return bool(self.tracker.seats)

    @property
    def staff_mode(self) -> bool:
        return bool(self.work) and bool(self.matcher.staff)

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
        self.work = work_areas_from_config(config)
        staff_settings = staff_settings_from_config(config)
        self.matcher.reconfigure(self.matcher.staff, staff_settings)
        self.presence.settings = staff_settings
        self.queue.areas, self.queue.settings = queue_areas_from_config(config), staff_settings
        self._load_detectors()

    def set_staff(self, staff: list[StaffMember]) -> None:
        self.matcher.reconfigure(staff, self.matcher.settings)

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
        self.people_seen = detections
        height, width = image.shape[:2]
        assignments = self.counter.update(detections, width, height, at) if self.counter.zones else []
        if self.staff_mode:
            self._track_staff(image, detections, width, height, at)
        if not self.seat_mode:
            self._time_stays(assignments, width, height, at)
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
        self._time_stays(assignments, width, height, at)
        return assignments

    def _time_stays(self, assignments: list[Assignment], width: int, height: int, at: float) -> None:
        staff = self.staff_tracks()
        seated = [
            (d.track_id, (d.x1 + d.x2) / 2 / width, d.y2 / height)
            for a in assignments
            if (d := a.detection).track_id is not None
            and d.track_id not in staff
            and a.zone_id is not None
            and a.reason != "standing"
        ]
        self.stay_times = self.stays.update(seated, at)

    def stay_labels(self) -> dict[int, str]:
        return {track: stay_text(seconds) for track, seconds in self.stay_times.items()}

    def _track_staff(self, image: np.ndarray, detections: list[Detection], width: int, height: int, at: float) -> None:
        workers = self.matcher.workers(detections, self.work, width, height)
        evidence = self.identity.read(image, workers) if self.identity is not None and workers else []
        seen = {
            d.track_id
            for d in detections
            if d.track_id is not None and d.confidence >= self.matcher.settings.min_confidence
        }
        named = self.matcher.update(workers, evidence, seen, at)
        self.named = named
        self.workers_seen = workers
        self.presence.update(list(named.values()), at)
        self.queue.update(detections, width, height, at, set(named))

    def staff_tracks(self) -> set[int]:
        return set(self.named) if self.staff_mode else set()

    def staff_snapshot(self, epoch_offset: float) -> dict[str, Any] | None:
        if not self.staff_mode:
            return None
        return {"presence": presence_payload(self.presence.drain(), epoch_offset), "queue": self.queue.reading()}

    def staff_labels(self) -> list[tuple[Detection, str]]:
        if not self.staff_mode:
            return []
        names = {s.staff_id: s.display_name for s in self.matcher.staff}
        return [
            (view.detection, f"{names.get(self.named[track_id][0], 'staff')} ({view.area})")
            for view in self.workers_seen
            if (track_id := view.detection.track_id) is not None and track_id in self.named
        ]

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
