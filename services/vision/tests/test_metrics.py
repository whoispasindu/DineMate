from vision.metrics import Sample, SeatSample, confusion, level_for, seat_table, summarize, summarize_seats, table


def sample(truth: int, estimate: int, low: int, high: int, capacity: int = 20) -> Sample:
    return Sample("lunch.mp4", 10.0, "Tables", truth, estimate, low, high, capacity)


def test_levels_follow_default_thresholds() -> None:
    assert [level_for(n, 20) for n in (11, 12, 16, 19)] == ["normal", "busy", "crowded", "near_capacity"]


def test_summary_metrics() -> None:
    summary = summarize(
        "lunch", [sample(10, 12, 9, 15), sample(10, 7, 5, 9), sample(16, 16, 14, 18), sample(4, 4, 3, 5)]
    )
    assert summary.samples == 4
    assert summary.mae == 1.25
    assert summary.bias == -0.25
    assert summary.within_2 == 0.75
    assert summary.coverage == 0.75
    assert summary.level_accuracy == 0.75


def test_empty_summary_and_table() -> None:
    assert summarize("none", []).samples == 0
    text = table([summarize("lunch", [sample(10, 12, 9, 15)])])
    assert "lunch" in text and "2.00" in text and "+2.00" in text


def seat(truth: str, estimate: str) -> SeatSample:
    return SeatSample("clip.mp4", 10.0, "seat-1", truth, estimate)


def test_seat_summary_counts_false_free_and_per_state() -> None:
    samples = [
        seat("free", "free"),
        seat("occupied", "occupied"),
        seat("held", "free"),
        seat("held", "held"),
        seat("occupied", "unknown"),
    ]
    summary = summarize_seats("clip", samples)
    assert summary.accuracy == 3 / 5
    assert summary.false_free == 1 / 5
    assert summary.hidden == 1 / 5
    assert summary.per_state == {"free": 1.0, "occupied": 0.5, "held": 0.5}
    assert "false free" in seat_table([summary])
    assert confusion(samples).splitlines()[3].split() == ["held", "1", "0", "1", "0"]
