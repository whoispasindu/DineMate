from vision.metrics import Sample, level_for, summarize, table


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
