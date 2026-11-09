from datetime import UTC, datetime, timedelta

from app.business.coverage import Interval, QueuePoint, coverage, merge, queue_alerts

T0 = datetime(2026, 11, 20, 1, 30, tzinfo=UTC)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def span(a: float, b: float) -> Interval:
    return Interval(at(a), at(b))


def test_overlapping_shifts_merge() -> None:
    assert merge([span(0, 30), span(20, 50), span(60, 70)]) == [span(0, 50), span(60, 70)]


def test_coverage_counts_staffed_minutes_and_long_gaps_only() -> None:
    result = coverage([span(0, 39), span(40, 70), span(76, 100)], [span(0, 100)])
    assert result.open_min == 100
    assert result.covered_min == 93
    assert result.gaps == [span(70, 76)]
    assert result.share == 0.93


def test_presence_outside_opening_hours_is_ignored() -> None:
    result = coverage([span(-30, 10), span(90, 130)], [span(0, 100)])
    assert result.covered_min == 20
    assert result.gaps == [span(10, 90)]


def test_unstaffed_day_is_one_gap_and_closed_day_has_no_share() -> None:
    assert coverage([], [span(0, 60)]).gaps == [span(0, 60)]
    assert coverage([span(0, 10)], []).share is None


def test_queue_alert_needs_the_queue_to_stay_long_for_a_minute() -> None:
    points = [QueuePoint(at(m / 6), n) for m, n in enumerate([3, 6, 7, 8, 7, 6, 6, 6, 2, 9, 9, 2])]
    alerts = queue_alerts(points, limit=5)
    assert len(alerts) == 1
    assert alerts[0].start == at(1 / 6)
    assert alerts[0].peak == 8


def test_queue_still_long_at_the_end_is_reported() -> None:
    points = [QueuePoint(at(m / 6), 7) for m in range(10)]
    (alert,) = queue_alerts(points, limit=5)
    assert alert.end == at(9 / 6)
