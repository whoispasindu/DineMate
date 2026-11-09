import pytest

from lab.compare import Mark, Sample, compare, csv_rows, truth_at

MARKS = [Mark(10.0, "seats", 2), Mark(30.0, "seats", 3), Mark(5.0, "queue", 0)]


def test_your_count_holds_until_you_change_it() -> None:
    assert truth_at(MARKS, "seats", 9.9) is None
    assert truth_at(MARKS, "seats", 10.0) == 2
    assert truth_at(MARKS, "seats", 29.0) == 2
    assert truth_at(MARKS, "seats", 31.0) == 3
    assert truth_at(MARKS, "other", 31.0) is None


def test_compare_starts_at_your_first_count_per_zone() -> None:
    samples = [Sample(t, {"seats": ours, "queue": 1}) for t, ours in ((0, 9), (12, 2), (20, 3), (35, 3), (40, 5))]
    seats, queue = compare(samples, MARKS, ["seats", "queue"])
    assert [p.t for p in seats.points] == [12, 20, 35, 40]
    assert seats.mae == pytest.approx((0 + 1 + 0 + 2) / 4)
    assert seats.bias == pytest.approx(0.75)
    assert seats.within_one == pytest.approx(0.75)
    assert seats.exact == pytest.approx(0.5)
    assert queue.n == 4 and queue.mae == pytest.approx(1.0)


def test_skip_ignores_the_warm_up_after_your_first_count() -> None:
    samples = [Sample(t, {"seats": 2}) for t in (10, 15, 25, 40)]
    (seats,) = compare(samples, MARKS, ["seats"], skip_s=10)
    assert [p.t for p in seats.points] == [25, 40]


def test_a_zone_you_never_counted_has_no_score() -> None:
    (empty,) = compare([Sample(1, {"bar": 4})], MARKS, ["bar"])
    assert empty.n == 0 and empty.mae is None and empty.summary()["within_one"] is None


def test_csv_has_one_row_per_zone_sample() -> None:
    rows = csv_rows([Sample(12.04, {"seats": 2, "queue": 1})], MARKS, ["seats", "queue"])
    assert rows == [["t_s", "zone", "ours", "yours"], [12.0, "seats", 2, 2], [12.0, "queue", 1, 0]]
