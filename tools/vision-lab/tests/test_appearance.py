import numpy as np
import pytest

from lab.appearance import (
    Gallery,
    LookEnrolment,
    ReIdentifier,
    hs_histogram,
    mean_signature,
    signature_from_hsv,
    similarity,
)


def person(top_hue: int, bottom_hue: int, height: int = 120, width: int = 50) -> np.ndarray:
    hsv = np.zeros((height, width, 3), dtype=np.uint8)
    hsv[:, :, 1] = 200
    hsv[:, :, 2] = 200
    hsv[: height // 2, :, 0] = top_hue
    hsv[height // 2 :, :, 0] = bottom_hue
    return hsv


def look(top: int, bottom: int) -> np.ndarray:
    sig = signature_from_hsv(person(top, bottom))
    assert sig is not None
    return sig


def test_histograms_ignore_dark_pixels_and_sum_to_one() -> None:
    hsv = person(10, 10)
    hsv[:20, :, 2] = 5
    hist = hs_histogram(hsv)
    assert hist.sum() == pytest.approx(1.0)
    assert hs_histogram(np.zeros((10, 10, 3), dtype=np.uint8)).sum() == 0


def test_signatures_tell_clothes_apart() -> None:
    red_blue = look(0, 110)
    assert similarity(red_blue, look(0, 110)) == pytest.approx(1.0)
    assert similarity(red_blue, look(60, 110)) == pytest.approx(0.5)
    assert similarity(red_blue, look(60, 30)) == pytest.approx(0.0)
    assert signature_from_hsv(person(0, 0, height=20)) is None


def test_gallery_needs_a_clear_winner() -> None:
    gallery = Gallery(threshold=0.6, margin=0.1)
    gallery.looks = {"Barista 1": look(0, 110), "Barista 2": look(60, 110)}
    assert gallery.accept(look(0, 110), set()) == ("Barista 1", pytest.approx(1.0))
    assert gallery.accept(look(0, 110), {"Barista 1"})[0] is None
    gallery.looks["Twin"] = look(0, 110)
    assert gallery.accept(look(0, 110), set())[0] is None


def test_reidentifier_waits_for_consistent_matches() -> None:
    gallery = Gallery()
    gallery.looks = {"Barista 1": look(0, 110)}
    reid = ReIdentifier(gallery, needed=3)
    assert reid.observe(7, look(0, 110), set()) is None
    assert reid.observe(7, look(60, 30), set()) is None
    assert reid.observe(7, look(0, 110), set()) is None
    assert reid.observe(7, look(0, 110), set()) is None
    assert reid.observe(7, look(0, 110), set()) == "Barista 1"
    reid.keep(set())
    assert reid.tries == {}


def test_look_enrolment_averages_consistent_samples_only() -> None:
    good = LookEnrolment("Barista 1", 3, 0.0, needed=4)
    for _ in range(4):
        good.add(look(0, 110))
    assert good.done(1.0)
    result = good.look()
    assert result is not None and result.sum() == pytest.approx(1.0)
    mixed = LookEnrolment("Barista 2", 4, 0.0)
    for top, bottom in ((0, 110), (60, 30), (120, 10)):
        mixed.add(look(top, bottom))
    assert mixed.look() is None
    assert LookEnrolment("X", 1, 0.0).look() is None
    assert not mixed.done(10.0) and mixed.done(16.0)
    assert mean_signature([look(0, 110), look(0, 110)]).sum() == pytest.approx(1.0)
