import numpy as np

from vision.counting import Detection
from vision.pipeline import Models, Pipeline
from vision.seats import ObjectDetection

W, H = 1000, 1000
IMAGE = np.zeros((H, W, 3), dtype=np.uint8)
CONFIG = {
    "zones": [
        {
            "zone_id": "tables",
            "name": "Tables",
            "capacity": 2,
            "points": [[0.0, 0.3], [0.5, 0.3], [0.5, 1.0], [0.0, 1.0]],
            "seats": [{"seat_id": "a", "x": 0.2, "y": 0.6}, {"seat_id": "b", "x": 0.4, "y": 0.6}],
        },
        {
            "zone_id": "bench",
            "name": "Bench",
            "capacity": 5,
            "points": [[0.5, 0.3], [1.0, 0.3], [1.0, 1.0], [0.5, 1.0]],
        },
    ],
    "ignore": [],
    "settings": {"dwell_s": 2, "clear_s": 3, "held_after_s": 2, "smoothing_s": 5, "objects_every_s": 0},
}


class FakePeople:
    imgsz = 640

    def __init__(self) -> None:
        self.people: list[Detection] = []

    def detect(self, image: np.ndarray) -> list[Detection]:
        return self.people


class FakeObjects:
    def __init__(self) -> None:
        self.objects: list[ObjectDetection] = []
        self.calls = 0

    def detect(self, image: np.ndarray) -> list[ObjectDetection]:
        self.calls += 1
        return self.objects


def seated_at(track: int, x: float, y: float) -> Detection:
    points = [(0.0, 0.0, 0.0)] * 17
    points[5], points[6] = (x - 20, y - 150, 0.9), (x + 20, y - 150, 0.9)
    points[11], points[12] = (x - 15, y, 0.9), (x + 15, y, 0.9)
    return Detection(track, x - 50, y - 220, x + 50, y + 40, 0.9, tuple(points))


def pipeline() -> tuple[Pipeline, FakePeople, FakeObjects]:
    people, objects = FakePeople(), FakeObjects()
    return Pipeline(CONFIG, Models("detect.pt", "pose.pt"), people, objects), people, objects


def test_seat_zones_and_plain_zones_are_counted_side_by_side() -> None:
    p, people, objects = pipeline()
    assert p.seat_mode
    assert [z.zone_id for z in p.counter.zones] == ["bench"]
    assert [z.zone_id for z in p.tracker.zones] == ["tables"]
    people.people = [seated_at(1, 200, 600), seated_at(2, 750, 500)]
    objects.objects = [ObjectDetection("handbag", 380, 580, 420, 620, 0.8)]
    for t in range(0, 8):
        p.process(IMAGE, float(t))
    readings = {r["zone_id"]: r for r in p.readings()}
    assert readings["tables"]["estimated_occupied"] == 2
    assert readings["bench"]["estimated_occupied"] == 1
    states = {seat.seat_id: state for seat, state in p.seat_states()}
    assert states == {"a": "occupied", "b": "held"}
    assert "1 held" in p.labels()["tables"]
    snapshot = p.snapshot(8.0)
    assert snapshot is not None
    assert snapshot["zones"][0]["held"] == 1


def test_layout_without_seats_keeps_zone_counting_only() -> None:
    plain = {**CONFIG, "zones": [CONFIG["zones"][1]]}
    p = Pipeline(plain, Models("detect.pt", "pose.pt"), FakePeople(), FakeObjects())
    assert not p.seat_mode
    assert p.snapshot(0.0) is None
    assert p.labels() == {}


def test_objects_are_detected_on_their_own_schedule() -> None:
    config = {**CONFIG, "settings": {**CONFIG["settings"], "objects_every_s": 5}}
    objects = FakeObjects()
    p = Pipeline(config, Models("detect.pt", "pose.pt"), FakePeople(), objects)
    for t in range(0, 11):
        p.process(IMAGE, float(t))
    assert objects.calls == 3


class SizedPeople(FakePeople):
    def __init__(self) -> None:
        super().__init__()
        self.requested_imgsz: int | None = None
        self.imgsz: int | None = 640


def test_detection_size_follows_the_camera_setting_unless_the_command_line_sets_it() -> None:
    people = SizedPeople()
    p = Pipeline(CONFIG, Models("detect.pt", "pose.pt"), people, FakeObjects())
    assert p.wanted_imgsz() is None and people.imgsz == 640
    p.configure({**CONFIG, "settings": {**CONFIG["settings"], "imgsz": 1280}})
    assert p.wanted_imgsz() == 1280 and people.requested_imgsz == 1280 and people.imgsz is None
    p.configure(CONFIG)
    assert people.requested_imgsz is None
    fixed = Pipeline(CONFIG, Models("detect.pt", "pose.pt", 960), SizedPeople(), FakeObjects())
    fixed.configure({**CONFIG, "settings": {**CONFIG["settings"], "imgsz": 1280}})
    assert fixed.wanted_imgsz() == 960
