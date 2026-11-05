from vision.detector import objects_from, people_from, pick_imgsz


def test_small_sources_use_640() -> None:
    assert pick_imgsz(640) == 640
    assert pick_imgsz(1280) == 640
    assert pick_imgsz(1919) == 640


def test_full_hd_and_4k_use_1280() -> None:
    assert pick_imgsz(1920) == 1280
    assert pick_imgsz(3840) == 1280


def test_explicit_size_wins() -> None:
    assert pick_imgsz(3840, 640) == 640
    assert pick_imgsz(640, 960) == 960


def test_people_carry_pose_keypoints_when_the_model_has_them() -> None:
    people = people_from([[0, 0, 10, 20]], [0.9], [7], [[[1, 2, 0.8]] * 17])
    assert people[0].track_id == 7
    assert people[0].keypoints is not None
    assert people[0].keypoints[0] == (1.0, 2.0, 0.8)
    assert people_from([[0, 0, 10, 20]], [0.9], [None], None)[0].keypoints is None


def test_only_belongings_and_tableware_are_kept() -> None:
    names = {0: "person", 24: "backpack", 41: "cup", 2: "car"}
    found = objects_from([[0, 0, 1, 1], [0, 0, 2, 2], [0, 0, 3, 3]], [24, 41, 2], [0.9, 0.8, 0.7], names)
    assert [o.label for o in found] == ["backpack", "cup"]
