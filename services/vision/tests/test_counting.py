from vision.counting import CountSettings, Detection, Zone, ZoneCounter, zones_from_config
from vision.geometry import contains

W, H = 1000, 1000
LEFT = Zone("left", "Left tables", 4, [(0.0, 0.4), (0.5, 0.4), (0.5, 1.0), (0.0, 1.0)])
RIGHT = Zone("right", "Right tables", 10, [(0.5, 0.4), (1.0, 0.4), (1.0, 1.0), (0.5, 1.0)])
WALKWAY = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.3), (0.0, 0.3)]


def person(track: int | None, cx: float, top: float, height: float = 200, conf: float = 0.8) -> Detection:
    return Detection(track, cx * W - 40, top * H, cx * W + 40, top * H + height, conf)


def counter(**overrides: float | None) -> ZoneCounter:
    settings = CountSettings(**{"dwell_s": 10.0, "smoothing_s": 60.0, **overrides})  # type: ignore[arg-type]
    return ZoneCounter([LEFT, RIGHT], [WALKWAY], settings)


def test_point_in_polygon() -> None:
    assert contains(LEFT.points, 0.25, 0.7)
    assert not contains(LEFT.points, 0.75, 0.7)
    assert not contains(LEFT.points, 0.25, 0.2)


def test_dwell_must_pass_before_counting() -> None:
    c = counter()
    first = c.update([person(1, 0.25, 0.5)], W, H, now=0)
    assert first[0].reason == "waiting for dwell"
    later = c.update([person(1, 0.25, 0.5)], W, H, now=10)
    assert later[0].counted
    assert c.readings()[0]["estimated_occupied"] in (0, 1)


def test_people_in_walkway_and_low_confidence_are_dropped() -> None:
    c = counter(dwell_s=0)
    result = c.update([person(1, 0.25, 0.05), person(2, 0.25, 0.5, conf=0.1), person(3, 0.25, 0.5)], W, H, now=0)
    assert [a.reason for a in result] == ["ignored area", "low confidence", "counted"]


def test_untracked_detections_are_not_counted() -> None:
    c = counter(dwell_s=0)
    assert c.update([person(None, 0.25, 0.5)], W, H, now=0)[0].reason == "not tracked yet"


def test_leaving_resets_dwell() -> None:
    c = counter()
    c.update([person(1, 0.25, 0.5)], W, H, now=0)
    c.update([], W, H, now=5)
    c.update([person(1, 0.25, 0.5)], W, H, now=12)
    assert not c.update([person(1, 0.25, 0.5)], W, H, now=13)[0].counted


def test_count_is_clamped_to_capacity() -> None:
    c = counter(dwell_s=0)
    c.update([person(i, 0.1 + i * 0.05, 0.5) for i in range(6)], W, H, now=0)
    left = next(r for r in c.readings() if r["zone_id"] == "left")
    assert left["estimated_occupied"] == 4
    assert left["occupied_high"] == 4


def test_standing_people_filtered_when_calibrated() -> None:
    c = counter(dwell_s=0, h_stand_a=0.0, h_stand_b=0.4, seated_ratio=0.7)
    seated = person(1, 0.25, 0.5, height=200)
    standing = person(2, 0.75, 0.5, height=380)
    reasons = [a.reason for a in c.update([seated, standing], W, H, now=0)]
    assert reasons == ["counted", "standing"]


def test_median_smoothing_ignores_a_brief_spike() -> None:
    c = counter(dwell_s=0)
    for t in range(10):
        people = [person(i, 0.55 + i * 0.04, 0.5) for i in range(8 if t == 5 else 2)]
        c.update(people, W, H, now=t)
    right = next(r for r in c.readings() if r["zone_id"] == "right")
    assert right["estimated_occupied"] == 2
    assert right["confidence"] == "medium"
    assert (right["occupied_low"], right["occupied_high"]) == (0, 4)


def test_old_samples_leave_the_window() -> None:
    c = counter(dwell_s=0, smoothing_s=5)
    c.update([person(1, 0.25, 0.5)], W, H, now=0)
    c.update([], W, H, now=10)
    left = next(r for r in c.readings() if r["zone_id"] == "left")
    assert (left["estimated_occupied"], left["samples"]) == (0, 1)


def test_config_parsing() -> None:
    zones, ignore, settings = zones_from_config(
        {
            "zones": [{"zone_id": "z", "name": "Desk", "capacity": 4, "points": [[0, 0], [1, 0], [1, 1]]}],
            "ignore": [{"type": "queue", "points": [[0, 0], [0.1, 0], [0.1, 0.1]]}],
            "settings": {"dwell_s": 12, "smoothing_s": 30, "h_stand_a": None},
        }
    )
    assert zones[0].capacity == 4 and len(ignore) == 1
    assert (settings.dwell_s, settings.smoothing_s, settings.h_stand_a) == (12, 30, None)
