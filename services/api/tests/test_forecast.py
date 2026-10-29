import math
import random
from datetime import UTC, date, datetime, time, timedelta

from app.services.forecast import Series, combine, evaluate, predict, slot_start
from app.services.timeutil import CAMPUS_TZ


def lunch_curve(t: datetime) -> float:
    local = t.astimezone(CAMPUS_TZ)
    hours = local.hour + local.minute / 60
    return 10 + 70 * math.exp(-(((hours - 12.75) / 0.9) ** 2))


def weekdays(start: date, days: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(days) if (start + timedelta(days=i)).weekday() < 5]


def build(days: list[date], noise: float = 0.0, seed: int = 7) -> Series:
    rng = random.Random(seed)
    points = {}
    for day in days:
        t = datetime.combine(day, time(10, 0), tzinfo=CAMPUS_TZ).astimezone(UTC)
        end = datetime.combine(day, time(15, 0), tzinfo=CAMPUS_TZ).astimezone(UTC)
        while t < end:
            points[t] = max(0.0, lunch_curve(t) + rng.gauss(0, noise))
            t += timedelta(minutes=10)
    return Series(points)


def test_slot_start_floors_to_ten_minutes() -> None:
    assert slot_start(datetime(2026, 11, 20, 7, 17, 42, 5, tzinfo=UTC)) == datetime(2026, 11, 20, 7, 10, tzinfo=UTC)


def test_combine_falls_back_cleanly() -> None:
    assert combine(None, None, 0.5) is None
    assert combine(40, None, 0.5) == (40.0, "persistence")
    assert combine(None, 30, 0.5) == (30, "historical")
    assert combine(40, 20, 0.25) == (25.0, "blend")


def test_historical_uses_only_the_past() -> None:
    days = weekdays(date(2026, 10, 26), 21)
    series = build(days)
    target = datetime.combine(days[-1], time(12, 40), tzinfo=CAMPUS_TZ).astimezone(UTC)
    before = datetime.combine(days[-1], time(12, 0), tzinfo=CAMPUS_TZ).astimezone(UTC)
    expected = lunch_curve(target)
    assert abs((series.historical(target, before) or 0) - expected) < 0.01
    early = datetime.combine(days[0], time(12, 0), tzinfo=CAMPUS_TZ).astimezone(UTC)
    assert series.historical(target, early) is None
    tampered = Series({**series.points, target: 0.0})
    assert tampered.historical(target, before) == series.historical(target, before)


def test_predict_without_history_is_persistence_with_a_band() -> None:
    now = datetime(2026, 11, 20, 7, 0, tzinfo=UTC)
    out = predict(Series({}), now, 55.0)
    assert [p.horizon for p in out] == [15, 30, 45, 60]
    assert all(p.model == "persistence" and p.low < 55 < p.high for p in out)
    assert predict(Series({}), now, None) == []


def test_blend_beats_persistence_on_a_lunch_curve() -> None:
    series = build(weekdays(date(2026, 10, 5), 42), noise=4.0)
    result = evaluate(series)
    assert result.params.fitted and result.train_until is not None
    by_h = {s.horizon: s for s in result.scores}
    for horizon in (30, 45, 60):
        score = by_h[horizon]
        assert score.samples > 50
        assert score.mae_blend is not None and score.mae_persistence is not None and score.mae_historical is not None
        assert score.mae_blend <= score.mae_persistence
        assert score.mae_blend <= score.mae_historical + 0.5
    assert all(s.coverage is not None and 0.6 <= s.coverage <= 0.95 for s in result.scores)


def test_evaluate_with_little_data_keeps_defaults() -> None:
    result = evaluate(build(weekdays(date(2026, 11, 16), 3)))
    assert result.params.fitted is False
