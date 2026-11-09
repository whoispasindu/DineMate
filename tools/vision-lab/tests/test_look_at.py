import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services" / "vision"))

cv2 = pytest.importorskip("cv2")

from lab.appearance import similarity  # noqa: E402
from lab.session import look_at, photo_of  # noqa: E402
from vision.counting import Detection  # noqa: E402


def frame_with_person(shirt: tuple[int, int, int]) -> np.ndarray:
    image = np.full((360, 640, 3), 40, dtype=np.uint8)
    image[100:200, 300:360] = shirt
    image[200:300, 300:360] = (120, 60, 20)
    return image


def test_look_at_reads_a_person_and_ignores_missing_tracks() -> None:
    person = {7: Detection(7, 300, 100, 360, 300, 0.9)}
    red, again, green = (frame_with_person(c) for c in ((30, 30, 200), (30, 30, 200), (30, 200, 30)))
    sig_red, region = look_at(red, person, 7)
    sig_again, _ = look_at(again, person, 7)
    sig_green, _ = look_at(green, person, 7)
    assert sig_red is not None and region.shape[:2] == (200, 60)
    assert similarity(sig_red, sig_again) == pytest.approx(1.0)
    assert similarity(sig_red, sig_green) < 0.7
    assert look_at(red, person, 8) == (None, None)
    photo = photo_of(region)
    assert photo is not None and photo[:2] == b"\xff\xd8"
