from vision.posture import PostureSettings, classify, hip_point, knee_angle

SETTINGS = PostureSettings()
NOT_SEEN = (0.0, 0.0, 0.0)


def body(
    shoulders: float = 300,
    hips: float = 450,
    knees: tuple[float, float] | None = None,
    ankles: tuple[float, float] | None = None,
) -> tuple[tuple[float, float, float], ...]:
    points = [NOT_SEEN] * 17
    points[5], points[6] = (480, shoulders, 0.9), (520, shoulders, 0.9)
    points[11], points[12] = (485, hips, 0.9), (515, hips, 0.9)
    if knees:
        points[13], points[14] = (485 + knees[0], knees[1], 0.9), (515 + knees[0], knees[1], 0.9)
    if ankles:
        points[15], points[16] = (485 + ankles[0], ankles[1], 0.9), (515 + ankles[0], ankles[1], 0.9)
    return tuple(points)


BOX = (450.0, 250.0, 550.0, 700.0)


def test_knee_angle_straight_and_bent() -> None:
    assert round(knee_angle((0, 0), (0, 100), (0, 200))) == 180
    assert round(knee_angle((0, 0), (0, 100), (100, 100))) == 90


def test_straight_legs_mean_standing() -> None:
    assert classify(BOX, body(knees=(0, 570), ankles=(0, 690)), 1000, SETTINGS) == "standing"


def test_bent_knees_mean_seated() -> None:
    assert classify(BOX, body(knees=(120, 460), ankles=(120, 580)), 1000, SETTINGS) == "seated"


def test_hips_well_above_the_seat_mean_standing() -> None:
    assert classify(BOX, body(hips=450), 1000, SETTINGS, seat_y=600) == "standing"
    assert classify(BOX, body(hips=590), 1000, SETTINGS, seat_y=600) == "seated"


def test_conflicting_signals_are_unsure() -> None:
    standing_legs = body(hips=595, knees=(0, 700), ankles=(0, 820))
    assert classify(BOX, standing_legs, 1000, SETTINGS, seat_y=600) == "unsure"


def test_no_keypoints_falls_back_to_height_calibration() -> None:
    calibrated = PostureSettings(h_stand_a=0.0, h_stand_b=0.5)
    assert classify((0, 400, 100, 600), None, 1000, calibrated) == "seated"
    assert classify((0, 100, 100, 600), None, 1000, calibrated) == "standing"
    assert classify((0, 400, 100, 600), None, 1000, SETTINGS) == "unsure"


def test_hip_point_uses_keypoints_then_the_box() -> None:
    assert hip_point(BOX, body(hips=450)) == (500.0, 450.0)
    assert hip_point((0, 0, 100, 400), None) == (50.0, 300.0)
