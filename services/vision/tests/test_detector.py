from vision.detector import pick_imgsz


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
