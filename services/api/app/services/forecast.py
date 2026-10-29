from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from statistics import mean

from app.services.timeutil import CAMPUS_TZ

SLOT = timedelta(minutes=10)
HORIZONS = (15, 30, 45, 60)
DEFAULT_ALPHA = {15: 0.7, 30: 0.5, 45: 0.35, 60: 0.25}
DEFAULT_BAND = {15: 6.0, 30: 9.0, 45: 11.0, 60: 13.0}
MIN_SAME_WEEKDAY = 2
MIN_ANY_WEEKDAY = 3
MIN_FIT_SAMPLES = 20
ALPHA_GRID = [i / 20 for i in range(21)]
COVERAGE = 0.8


def slot_start(t: datetime) -> datetime:
    return t - timedelta(minutes=t.minute % 10, seconds=t.second, microseconds=t.microsecond)


def _key(t: datetime) -> tuple[int, time]:
    local = t.astimezone(CAMPUS_TZ)
    return local.weekday(), local.time().replace(second=0, microsecond=0)


@dataclass
class Series:
    points: dict[datetime, float]
    _by_weekday: dict[tuple[int, time], list[tuple[datetime, float]]] = field(init=False)
    _by_day_type: dict[tuple[bool, time], list[tuple[datetime, float]]] = field(init=False)

    def __post_init__(self) -> None:
        self._by_weekday = defaultdict(list)
        self._by_day_type = defaultdict(list)
        for t in sorted(self.points):
            weekday, tod = _key(t)
            self._by_weekday[(weekday, tod)].append((t, self.points[t]))
            self._by_day_type[(weekday >= 5, tod)].append((t, self.points[t]))

    def historical(self, target: datetime, before: datetime) -> float | None:
        weekday, tod = _key(slot_start(target))
        same = _before(self._by_weekday.get((weekday, tod), []), before)
        if len(same) >= MIN_SAME_WEEKDAY:
            return mean(same)
        any_day = _before(self._by_day_type.get((weekday >= 5, tod), []), before)
        return mean(any_day) if len(any_day) >= MIN_ANY_WEEKDAY else None


def _before(rows: list[tuple[datetime, float]], before: datetime) -> list[float]:
    cut = bisect_left(rows, before, key=lambda r: r[0])
    return [v for _, v in rows[:cut]]


@dataclass(frozen=True)
class Params:
    alpha: dict[int, float]
    band: dict[int, float]
    fitted: bool


DEFAULT_PARAMS = Params(alpha=DEFAULT_ALPHA, band=DEFAULT_BAND, fitted=False)


@dataclass(frozen=True)
class Prediction:
    at: datetime
    horizon: int
    mean: float
    low: int
    high: int
    model: str


def _clamp(value: float) -> int:
    return round(min(100.0, max(0.0, value)))


def combine(current: float | None, historical: float | None, alpha: float) -> tuple[float, str] | None:
    if current is None and historical is None:
        return None
    if historical is None:
        return float(current or 0.0), "persistence"
    if current is None:
        return historical, "historical"
    return alpha * current + (1 - alpha) * historical, "blend"


def predict(series: Series, now: datetime, current: float | None, params: Params = DEFAULT_PARAMS) -> list[Prediction]:
    out = []
    for horizon in HORIZONS:
        target = now + timedelta(minutes=horizon)
        result = combine(current, series.historical(target, now), params.alpha[horizon])
        if result is None:
            continue
        value, model = result
        band = params.band[horizon]
        out.append(Prediction(target, horizon, value, _clamp(value - band), _clamp(value + band), model))
    return out


@dataclass(frozen=True)
class HorizonScore:
    horizon: int
    samples: int
    mae_persistence: float | None
    mae_historical: float | None
    mae_blend: float | None
    alpha: float
    band: float
    coverage: float | None


@dataclass(frozen=True)
class Evaluation:
    train_until: datetime | None
    scores: list[HorizonScore]
    params: Params


def _cases(
    series: Series, horizon: int, start: datetime | None, end: datetime | None
) -> list[tuple[float, float, float]]:
    cases = []
    for t, current in series.points.items():
        if (start is not None and t < start) or (end is not None and t >= end):
            continue
        actual = series.points.get(slot_start(t + timedelta(minutes=horizon)))
        historical = series.historical(t + timedelta(minutes=horizon), t)
        if actual is not None and historical is not None:
            cases.append((current, historical, actual))
    return cases


def _mae(errors: list[float]) -> float | None:
    return round(mean(errors), 2) if errors else None


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def evaluate(series: Series, test_days: int = 7) -> Evaluation:
    if not series.points:
        return Evaluation(None, [], DEFAULT_PARAMS)
    last = max(series.points)
    split = last - timedelta(days=test_days)
    alpha, band, scores = dict(DEFAULT_ALPHA), dict(DEFAULT_BAND), []
    fitted = True
    for horizon in HORIZONS:
        train = _cases(series, horizon, split - timedelta(days=test_days), split)
        if len(train) < MIN_FIT_SAMPLES:
            train = _cases(series, horizon, None, split)
        test = _cases(series, horizon, split, None)
        if len(train) >= MIN_FIT_SAMPLES:
            alpha[horizon] = min(ALPHA_GRID, key=lambda a: mean(abs(a * c + (1 - a) * h - y) for c, h, y in train))
            band[horizon] = round(
                _quantile([abs(alpha[horizon] * c + (1 - alpha[horizon]) * h - y) for c, h, y in train], COVERAGE), 1
            )
        else:
            fitted = False
        a, b = alpha[horizon], band[horizon]
        blend_errors = [abs(a * c + (1 - a) * h - y) for c, h, y in test]
        scores.append(
            HorizonScore(
                horizon=horizon,
                samples=len(test),
                mae_persistence=_mae([abs(c - y) for c, _, y in test]),
                mae_historical=_mae([abs(h - y) for _, h, y in test]),
                mae_blend=_mae(blend_errors),
                alpha=a,
                band=b,
                coverage=round(sum(1 for e in blend_errors if e <= b) / len(blend_errors), 2) if blend_errors else None,
            )
        )
    return Evaluation(split, scores, Params(alpha=alpha, band=band, fitted=fitted))
