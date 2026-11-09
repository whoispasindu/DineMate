import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services" / "vision"))

from lab.workers import Coverage, Enrolment, WorkerBook


def test_workers_get_anonymous_labels_and_time_per_area() -> None:
    book = WorkerBook()
    book.update([(1, "counter", 0.5, 0.3), (2, "kitchen", 0.8, 0.3)], {}, 0.0, True)
    book.update([(1, "counter", 0.5, 0.3), (2, "kitchen", 0.8, 0.3)], {}, 1.0, True)
    book.update([(1, "floor", 0.4, 0.6)], {}, 2.0, True)
    first, second = book.summary(2.0, min_seconds=0.5)["workers"]
    assert book.summary(2.0)["brief"] == 2
    assert first["label"] == "Worker 1" and first["seconds"]["counter"] == 1.0 and first["seconds"]["floor"] == 1.0
    assert second["label"] == "Worker 2" and second["seconds"]["kitchen"] == 1.0
    assert book.labels() == {1: "Worker 1 · floor · 0 min"}


def test_an_id_switch_nearby_keeps_the_same_worker() -> None:
    book = WorkerBook()
    book.update([(1, "counter", 0.5, 0.3)], {}, 0.0, True)
    book.update([], {}, 1.0, True)
    book.update([(9, "counter", 0.52, 0.31)], {}, 2.0, True)
    assert book.labels() == {9: "Worker 1 · counter · 0 min"}
    assert len(book.summary(2.0, min_seconds=0)["workers"]) == 1


def test_a_name_from_recognition_replaces_the_label() -> None:
    book = WorkerBook()
    book.update([(3, "counter", 0.5, 0.3)], {3: "Barista 1"}, 0.0, True)
    book.update([(3, "counter", 0.5, 0.3)], {}, 1.0, True)
    assert book.labels()[3].startswith("Barista 1 · counter")


def test_coverage_counts_counter_gaps_longer_than_the_minimum() -> None:
    coverage = Coverage(min_gap_s=10)
    for t in range(0, 61):
        staffed = not (20 <= t < 45 or 50 <= t < 55)
        coverage.update(staffed, float(t), 1.0 if t else 0.0)
    coverage.finish(60.0)
    summary = coverage.summary(60.0)
    assert summary["gaps"] == [[20.0, 45.0]]
    assert summary["staffed_s"] == pytest.approx(30.0)
    assert summary["share"] == pytest.approx(0.5)


def test_an_open_gap_shows_until_someone_returns() -> None:
    coverage = Coverage(min_gap_s=5)
    coverage.update(True, 0.0, 0.0)
    coverage.update(False, 1.0, 1.0)
    assert coverage.summary(10.0)["gaps"] == [[1.0, 10.0]]


def test_enrolment_needs_consistent_shots() -> None:
    good = Enrolment("Barista 1", 4, 0.0, needed=3)
    for angle in (0.0, 0.1, 0.2):
        good.add([math.cos(angle), math.sin(angle), 0.0])
    assert good.done(1.0)
    template = good.template()
    assert template is not None and abs(sum(v * v for v in template) - 1) < 1e-9
    mixed = Enrolment("Barista 2", 5, 0.0)
    mixed.add([1.0, 0.0, 0.0])
    mixed.add([0.0, 1.0, 0.0])
    assert mixed.template() is None
    assert not mixed.done(5.0) and mixed.done(25.0)
