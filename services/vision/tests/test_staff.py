from collections.abc import Sequence
from datetime import datetime

import numpy as np

from vision.counting import Detection, zones_from_config
from vision.pipeline import Models, Pipeline
from vision.staff import (
    Evidence,
    PresenceTracker,
    QueueCounter,
    StaffMatcher,
    StaffMember,
    StaffSettings,
    WorkArea,
    WorkerView,
    presence_payload,
    queue_areas_from_config,
    staff_from_response,
    staff_settings_from_config,
    work_areas_from_config,
)

W, H = 1000, 1000
IMAGE = np.zeros((H, W, 3), dtype=np.uint8)
COUNTER = WorkArea("counter", [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)])
KITCHEN = WorkArea("kitchen", [(0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (0.5, 0.5)])
QUEUE = [(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)]
ANA_FACE = (1.0, 0.0, 0.0, 0.0)
BEN_FACE = (0.0, 1.0, 0.0, 0.0)
STAFF = [
    StaffMember("ana", "Ana", "face", None, ANA_FACE),
    StaffMember("ben", "Ben", "face", None, BEN_FACE),
    StaffMember("cy", "Cy", "badge", 17),
]
SETTINGS = StaffSettings(confirm_matches=3, release_misses=2, lost_after_s=2.0, min_dwell_s=5.0, absence_s=10.0)


def person(track: int | None, fx: float, fy: float, confidence: float = 0.9) -> Detection:
    x, y = fx * W, fy * H
    return Detection(track, x - 40, y - 300, x + 40, y, confidence)


def matcher() -> StaffMatcher:
    return StaffMatcher(list(STAFF), SETTINGS)


def step(m: StaffMatcher, people: list[Detection], evidence: list[Evidence], now: float) -> dict[int, tuple[str, str]]:
    workers = m.workers(people, [COUNTER, KITCHEN], W, H)
    seen = {d.track_id for d in people if d.track_id is not None}
    return dict(m.update(workers, evidence, seen, now))


def face(track: int, vector: tuple[float, ...]) -> Evidence:
    return Evidence(track, embedding=vector)


def test_track_is_named_only_after_consistent_matches() -> None:
    m = matcher()
    ana = person(1, 0.2, 0.3)
    assert step(m, [ana], [face(1, ANA_FACE)], 0.0) == {}
    assert step(m, [ana], [face(1, ANA_FACE)], 1.0) == {}
    assert step(m, [ana], [face(1, ANA_FACE)], 2.0) == {1: ("ana", "counter")}


def test_a_different_match_restarts_the_streak_and_weak_scores_do_not_count() -> None:
    m = matcher()
    ana = person(1, 0.2, 0.3)
    step(m, [ana], [face(1, ANA_FACE)], 0.0)
    step(m, [ana], [face(1, ANA_FACE)], 1.0)
    step(m, [ana], [face(1, BEN_FACE)], 2.0)
    assert step(m, [ana], [face(1, ANA_FACE)], 3.0) == {}
    blurry = (0.5, 0.5, 0.7, 0.5)
    assert m.match(face(1, blurry)) is None
    assert m.match(face(1, (0.9, 0.1, 0.0, 0.0))) == "ana"


def test_named_track_keeps_its_name_through_one_miss_and_loses_it_after_more() -> None:
    m = matcher()
    ana = person(1, 0.2, 0.3)
    for t in range(3):
        step(m, [ana], [face(1, ANA_FACE)], float(t))
    stranger = (0.0, 0.0, 1.0, 0.0)
    assert step(m, [ana], [face(1, stranger)], 3.0) == {1: ("ana", "counter")}
    assert step(m, [ana], [], 4.0) == {1: ("ana", "counter")}
    assert step(m, [ana], [face(1, stranger)], 5.0) == {}


def test_badges_name_tracks_and_unknown_codes_do_not() -> None:
    m = matcher()
    cy = person(4, 0.7, 0.3)
    for t in range(3):
        named = step(m, [cy], [Evidence(4, badge_code=17)], float(t))
    assert named == {4: ("cy", "kitchen")}
    assert m.match(Evidence(4, badge_code=99)) is None


def test_customers_outside_work_areas_are_never_named() -> None:
    m = matcher()
    customer = person(7, 0.2, 0.8)
    for t in range(5):
        named = step(m, [customer], [face(7, ANA_FACE)], float(t))
    assert named == {}
    assert 7 not in m.tracks
    assert m.workers([customer], [COUNTER, KITCHEN], W, H) == []


def test_identity_is_dropped_when_a_named_worker_steps_out_of_work_areas() -> None:
    m = matcher()
    for t in range(3):
        step(m, [person(1, 0.2, 0.3)], [face(1, ANA_FACE)], float(t))
    assert step(m, [person(1, 0.2, 0.8)], [], 3.0) == {}
    assert step(m, [person(1, 0.2, 0.3)], [], 4.0) == {}


def test_identity_is_forgotten_when_the_track_is_lost() -> None:
    m = matcher()
    for t in range(3):
        step(m, [person(1, 0.2, 0.3)], [face(1, ANA_FACE)], float(t))
    assert step(m, [], [], 3.5) == {}
    assert 1 in m.tracks
    assert step(m, [person(1, 0.2, 0.3)], [], 4.0) == {1: ("ana", "counter")}
    step(m, [], [], 7.0)
    assert m.tracks == {}
    assert step(m, [person(1, 0.2, 0.3)], [], 8.0) == {}


def test_one_worker_names_one_track_at_a_time() -> None:
    m = matcher()
    for t in range(3):
        step(m, [person(1, 0.2, 0.3), person(2, 0.7, 0.3)], [face(1, ANA_FACE)], float(t))
    for t in range(3, 6):
        named = step(m, [person(1, 0.2, 0.3), person(2, 0.7, 0.3)], [face(2, ANA_FACE)], float(t))
    assert named == {2: ("ana", "kitchen")}


def test_removed_staff_lose_their_names() -> None:
    m = matcher()
    for t in range(3):
        step(m, [person(1, 0.2, 0.3)], [face(1, ANA_FACE)], float(t))
    m.reconfigure([s for s in STAFF if s.staff_id != "ana"], SETTINGS)
    assert step(m, [person(1, 0.2, 0.3)], [], 3.0) == {}


def test_presence_opens_after_dwell_and_closes_after_absence() -> None:
    p = PresenceTracker(SETTINGS)
    for t in range(0, 4):
        p.update([("ana", "counter")], float(t))
    assert p.drain() == []
    for t in range(4, 8):
        p.update([("ana", "counter")], float(t))
    assert p.drain() == [{"staff_id": "ana", "area": "counter", "started_at": 0.0, "ended_at": None}]
    p.update([], 15.0)
    assert p.drain() == [{"staff_id": "ana", "area": "counter", "started_at": 0.0, "ended_at": None}]
    p.update([], 18.0)
    assert p.drain() == [{"staff_id": "ana", "area": "counter", "started_at": 0.0, "ended_at": 7.0}]
    assert p.drain() == []


def test_short_visits_and_gaps_shorter_than_absence() -> None:
    p = PresenceTracker(SETTINGS)
    p.update([("ben", "kitchen")], 0.0)
    p.update([("ben", "kitchen")], 2.0)
    p.update([], 20.0)
    assert p.drain() == []
    p.update([("ben", "kitchen")], 30.0)
    p.update([("ben", "kitchen")], 38.0)
    p.update([("ben", "kitchen")], 45.0)
    rows = p.drain()
    assert rows == [{"staff_id": "ben", "area": "kitchen", "started_at": 30.0, "ended_at": None}]


def test_moving_between_areas_closes_the_old_interval() -> None:
    p = PresenceTracker(SETTINGS)
    for t in range(0, 7):
        p.update([("ana", "counter")], float(t))
    for t in range(7, 25):
        p.update([("ana", "kitchen")], float(t))
    rows = p.drain()
    assert {"staff_id": "ana", "area": "counter", "started_at": 0.0, "ended_at": 6.0} in rows
    assert {"staff_id": "ana", "area": "kitchen", "started_at": 7.0, "ended_at": None} in rows


def test_presence_payload_uses_wall_clock_iso_times() -> None:
    rows = [{"staff_id": "ana", "area": "counter", "started_at": 10.0, "ended_at": 70.0}]
    payload = presence_payload(rows, 1_700_000_000.0)
    started = datetime.fromisoformat(payload[0]["started_at"])
    ended = datetime.fromisoformat(payload[0]["ended_at"])
    assert (ended - started).total_seconds() == 60
    assert started.utcoffset() is not None


def test_queue_counts_feet_in_queue_polygons_and_skips_staff() -> None:
    q = QueueCounter([QUEUE], SETTINGS)
    people = [person(1, 0.2, 0.8), person(2, 0.3, 0.9), person(3, 0.8, 0.8), person(4, 0.2, 0.7, 0.1)]
    assert q.count(people, W, H) == 2
    assert q.count(people, W, H, {2}) == 1
    standing_over_line = Detection(5, 160, 200, 240, 450, 0.9)
    assert q.count([standing_over_line], W, H) == 0


def test_queue_reading_is_a_median_over_the_window() -> None:
    q = QueueCounter([QUEUE], StaffSettings(queue_window_s=10))
    for t, n in enumerate([1, 3, 3, 3, 8]):
        q.update([person(i, 0.1 + 0.05 * i, 0.8) for i in range(n)], W, H, float(t), set())
    assert q.reading() == {"people": 3}
    assert QueueCounter([], SETTINGS).reading() is None


def test_work_and_queue_areas_from_config() -> None:
    config = {
        "zones": [],
        "work": [{"area": "counter", "points": [[0, 0], [0.5, 0], [0.5, 0.5]]}],
        "ignore": [
            {"type": "work", "area": "kitchen", "points": [[0.5, 0], [1, 0], [1, 0.5]]},
            {"type": "work", "area": "roof", "points": [[0, 0], [1, 0], [1, 1]]},
            {"type": "queue", "points": [[0, 0.5], [0.5, 0.5], [0.5, 1]]},
            {"type": "walkway", "points": [[0, 0], [0.1, 0], [0.1, 0.1]]},
        ],
        "settings": {"face_threshold": 0.7, "confirm_matches": 4, "staff_dwell_s": 30},
    }
    assert [w.area for w in work_areas_from_config(config)] == ["counter", "kitchen"]
    assert work_areas_from_config(config)[0].points[1] == (0.5, 0.0)
    assert queue_areas_from_config(config) == [[(0.0, 0.5), (0.5, 0.5), (0.5, 1.0)]]
    settings = staff_settings_from_config(config)
    assert (settings.face_threshold, settings.confirm_matches, settings.min_dwell_s) == (0.7, 4, 30.0)
    _zones, ignore, _settings = zones_from_config(config)
    assert len(ignore) == 2


def test_staff_from_templates_response() -> None:
    payload = {
        "staff": [
            {"staff_id": "a", "display_name": "Ana", "method": "face", "badge_code": None, "template": [0.6, 0.8]},
            {"staff_id": "b", "display_name": "Ben", "method": "badge", "badge_code": 5, "template": None},
            {"staff_id": "c", "display_name": "Cy", "method": "face", "badge_code": None, "template": None},
            {"staff_id": "d", "display_name": "Di", "method": "badge", "badge_code": None, "template": None},
        ]
    }
    staff = staff_from_response(payload)
    assert [s.staff_id for s in staff] == ["a", "b"]
    assert staff[0].template == (0.6, 0.8) and staff[0].badge_code is None
    assert staff[1].badge_code == 5 and staff[1].template is None
    assert staff_from_response(payload["staff"]) == staff


class FakePeople:
    imgsz = 640

    def __init__(self) -> None:
        self.people: list[Detection] = []

    def detect(self, image: np.ndarray) -> list[Detection]:
        return self.people


class FakeReader:
    def __init__(self) -> None:
        self.asked: list[int | None] = []

    def read(self, image: np.ndarray, people: Sequence[WorkerView]) -> list[Evidence]:
        self.asked.extend(v.detection.track_id for v in people)
        return [Evidence(v.detection.track_id, embedding=ANA_FACE) for v in people if v.detection.track_id]


PIPELINE_CONFIG = {
    "zones": [],
    "ignore": [{"type": "queue", "points": [list(p) for p in QUEUE]}],
    "work": [{"area": "counter", "points": [list(p) for p in COUNTER.points]}],
    "settings": {"confirm_matches": 2, "staff_dwell_s": 2, "staff_absence_s": 5},
}


def test_pipeline_staff_mode_needs_work_areas_and_staff() -> None:
    no_staff = Pipeline(PIPELINE_CONFIG, Models("d.pt", "p.pt"), FakePeople(), identity=FakeReader())
    assert not no_staff.staff_mode
    assert no_staff.staff_snapshot(0.0) is None
    no_work = {**PIPELINE_CONFIG, "work": []}
    p = Pipeline(no_work, Models("d.pt", "p.pt"), FakePeople(), identity=FakeReader(), staff=list(STAFF))
    assert not p.staff_mode


def test_pipeline_names_workers_counts_the_queue_and_reads_only_work_areas() -> None:
    people, reader = FakePeople(), FakeReader()
    p = Pipeline(PIPELINE_CONFIG, Models("d.pt", "p.pt"), people, identity=reader, staff=list(STAFF))
    assert p.staff_mode
    people.people = [person(1, 0.2, 0.3), person(2, 0.2, 0.8), person(3, 0.3, 0.9)]
    for t in range(5):
        p.process(IMAGE, float(t))
    assert set(reader.asked) == {1}
    labels = p.staff_labels()
    assert [(d.track_id, text) for d, text in labels] == [(1, "Ana (counter)")]
    snapshot = p.staff_snapshot(1_700_000_000.0)
    assert snapshot is not None
    assert snapshot["queue"] == {"people": 2}
    assert [(r["staff_id"], r["area"], r["ended_at"]) for r in snapshot["presence"]] == [("ana", "counter", None)]
    p.set_staff([])
    assert not p.staff_mode and p.staff_labels() == []
