from vision.counting import Detection, Zone
from vision.seats import (
    ObjectDetection,
    Seat,
    SeatObservation,
    SeatSettings,
    SeatTrack,
    SeatTracker,
    seats_from_config,
    step,
    zone_reading,
)

W, H = 1000, 1000
SETTINGS = SeatSettings(dwell_s=10, return_s=3, clear_s=30, held_after_s=20, hidden_free_s=10, hidden_hold_s=120)
ZONE = Zone("z", "Tables", 4, [(0.0, 0.3), (1.0, 0.3), (1.0, 1.0), (0.0, 1.0)])
SEATS = [Seat("a", "z", 0.2, 0.6), Seat("b", "z", 0.4, 0.6), Seat("c", "z", 0.6, 0.6), Seat("d", "z", 0.8, 0.6)]


def run(track: SeatTrack, obs: SeatObservation, start: float, end: float, every: float = 1.0) -> SeatTrack:
    t = start
    while t <= end:
        step(track, obs, t, SETTINGS)
        t += every
    return track


def free_track() -> SeatTrack:
    return run(SeatTrack(), SeatObservation(), 0, 30)


def test_empty_seat_becomes_free_only_after_clear_time() -> None:
    track = run(SeatTrack(), SeatObservation(), 0, 29)
    assert track.state == "unknown"
    assert run(track, SeatObservation(), 30, 30).state == "free"


def test_person_must_stay_for_the_dwell_time() -> None:
    track = free_track()
    run(track, SeatObservation(person=True), 31, 40)
    assert track.state == "free"
    run(track, SeatObservation(person=True), 41, 41)
    assert track.state == "occupied"


def test_short_detection_gaps_do_not_reset_dwell() -> None:
    track = free_track()
    run(track, SeatObservation(person=True), 31, 35)
    run(track, SeatObservation(), 36, 37)
    run(track, SeatObservation(person=True), 38, 41)
    assert track.state == "occupied"


def test_bag_left_while_queuing_holds_the_seat_and_owner_returns() -> None:
    track = free_track()
    run(track, SeatObservation(person=True), 31, 45)
    run(track, SeatObservation(belongings=1), 46, 600)
    assert track.state == "held"
    run(track, SeatObservation(person=True), 601, 604)
    assert track.state == "occupied"


def test_bag_on_an_empty_seat_holds_it_after_a_wait() -> None:
    track = free_track()
    run(track, SeatObservation(belongings=1), 31, 50)
    assert track.state == "free"
    run(track, SeatObservation(belongings=1), 51, 51)
    assert track.state == "held"


def test_held_seat_frees_when_the_bag_is_gone() -> None:
    track = free_track()
    run(track, SeatObservation(belongings=1), 31, 60)
    run(track, SeatObservation(), 61, 89)
    assert track.state == "held"
    run(track, SeatObservation(), 90, 91)
    assert track.state == "free"


def test_a_passing_crowd_never_creates_a_free_seat() -> None:
    track = free_track()
    run(track, SeatObservation(person=True), 31, 45)
    run(track, SeatObservation(hidden=True), 46, 160)
    assert track.state == "occupied"
    run(track, SeatObservation(hidden=True), 161, 170)
    assert track.state == "unknown"
    run(track, SeatObservation(), 171, 171)
    assert track.state == "unknown"


def test_hidden_free_seat_turns_unknown() -> None:
    track = free_track()
    run(track, SeatObservation(hidden=True), 31, 40)
    assert track.state == "free"
    run(track, SeatObservation(hidden=True), 41, 41)
    assert track.state == "unknown"


def test_plates_left_behind_mean_free_soon_then_free() -> None:
    track = free_track()
    run(track, SeatObservation(person=True), 31, 45)
    run(track, SeatObservation(tableware=2), 46, 100)
    assert track.state == "occupied"
    assert track.free_soon
    run(track, SeatObservation(tableware=2), 101, 400)
    assert track.state == "free"


def test_zone_reading_never_counts_unknown_as_free() -> None:
    reading = zone_reading(ZONE, {"free": 1, "occupied": 1, "held": 1, "unknown": 1, "free_soon": 0})
    assert reading["estimated_occupied"] == 3
    assert (reading["occupied_low"], reading["occupied_high"]) == (2, 3)
    assert reading["confidence"] == "low"
    clear = zone_reading(ZONE, {"free": 3, "occupied": 1, "held": 0, "unknown": 0, "free_soon": 0})
    assert clear["confidence"] == "high"


def seated(track: int, seat: Seat) -> Detection:
    sx, sy = seat.x * W, seat.y * H
    points = [(0.0, 0.0, 0.0)] * 17
    points[5], points[6] = (sx - 20, sy - 150, 0.9), (sx + 20, sy - 150, 0.9)
    points[11], points[12] = (sx - 15, sy, 0.9), (sx + 15, sy, 0.9)
    return Detection(track, sx - 50, sy - 220, sx + 50, sy + 40, 0.9, tuple(points))


def standing_at(track: int, seat: Seat) -> Detection:
    sx, sy = seat.x * W, seat.y * H
    points = [(0.0, 0.0, 0.0)] * 17
    points[5], points[6] = (sx - 20, sy - 330, 0.9), (sx + 20, sy - 330, 0.9)
    points[11], points[12] = (sx - 15, sy - 180, 0.9), (sx + 15, sy - 180, 0.9)
    points[13], points[14] = (sx - 15, sy - 60, 0.9), (sx + 15, sy - 60, 0.9)
    points[15], points[16] = (sx - 15, sy + 60, 0.9), (sx + 15, sy + 60, 0.9)
    return Detection(track, sx - 50, sy - 400, sx + 50, sy + 70, 0.9, tuple(points))


def bag_at(seat: Seat) -> ObjectDetection:
    sx, sy = seat.x * W, seat.y * H
    return ObjectDetection("backpack", sx - 30, sy - 30, sx + 30, sy + 30, 0.8)


def tracker() -> SeatTracker:
    return SeatTracker([ZONE], SEATS, [], SETTINGS)


def play(t: SeatTracker, people: list[Detection], objects: list[ObjectDetection], start: float, end: float) -> None:
    now = start
    while now <= end:
        t.update(people, objects, W, H, now)
        now += 1


def test_tracker_counts_a_seated_person_not_a_standing_one() -> None:
    t = tracker()
    play(t, [], [], 0, 30)
    views = t.update([seated(1, SEATS[0]), standing_at(2, SEATS[2])], [], W, H, 31)
    assert [(v.posture, v.seat_id) for v in views] == [("seated", "a"), ("standing", None)]
    play(t, [seated(1, SEATS[0]), standing_at(2, SEATS[2])], [], 32, 45)
    counts = t.counts("z")
    assert counts["occupied"] == 1
    assert counts["free"] == 2
    assert counts["unknown"] == 1
    assert t.standing["z"] == 1


def test_tracker_marks_a_bag_only_seat_as_held() -> None:
    t = tracker()
    play(t, [], [], 0, 30)
    play(t, [], [bag_at(SEATS[1])], 31, 60)
    assert t.counts("z")["held"] == 1


def test_crowd_hiding_seats_is_reported() -> None:
    t = tracker()
    play(t, [], [], 0, 30)
    crowd = [standing_at(i, seat) for i, seat in enumerate(SEATS)]
    play(t, crowd, [], 31, 45)
    assert t.counts("z")["unknown"] == 4
    assert t.crowded("z")
    assert t.readings()[0]["occupied_high"] == 4
    snapshot = t.snapshot(45)
    assert snapshot["zones"][0]["crowded"] is True
    assert {s["state"] for s in snapshot["seats"]} == {"unknown"}


def test_seats_are_read_from_the_layout_config() -> None:
    config = {"zones": [{"zone_id": "z", "seats": [{"seat_id": "a", "x": 0.2, "y": 0.6}]}]}
    assert seats_from_config(config) == [Seat("a", "z", 0.2, 0.6)]
