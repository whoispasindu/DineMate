import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import quantiles

MIN_POOL = 20
MIN_TAIL = 5
STEP_MIN = 5
EVAL_ELAPSED = (5.0, 15.0, 30.0)


@dataclass(frozen=True)
class PastVisit:
    hour: int
    minutes: float
    party_size: int


@dataclass(frozen=True)
class Backtest:
    predictions: int
    coverage: float
    mae_minutes: float


def party_bucket(size: int) -> int:
    return 0 if size <= 2 else 1 if size <= 4 else 2


def _near(hour: int, other: int) -> bool:
    diff = abs(hour - other) % 24
    return min(diff, 24 - diff) <= 1


def _pool(history: Sequence[PastVisit], party_size: int, hour: int) -> list[PastVisit]:
    bucket = party_bucket(party_size)
    same = [v for v in history if party_bucket(v.party_size) == bucket]
    near = [v for v in same if _near(v.hour, hour)]
    for candidate in (near, same, list(history)):
        if len(candidate) >= MIN_POOL:
            return candidate
    return []


def _quartiles(values: list[float]) -> tuple[float, float]:
    if len(values) == 1:
        return values[0], values[0]
    q = quantiles(values, n=4, method="inclusive")
    return q[0], q[2]


def remaining_range(
    history: Sequence[PastVisit], elapsed_min: float, party_size: int, hour: int, plates_left: bool = False
) -> tuple[int, int] | None:
    pool = _pool(history, party_size, hour)
    if not pool:
        return None
    longer = sorted(v.minutes - elapsed_min for v in pool if v.minutes > elapsed_min)
    if len(longer) < MIN_TAIL:
        return (0, STEP_MIN)
    low, high = _quartiles(longer)
    if plates_left:
        low = 0
    low_r = int(math.floor(low / STEP_MIN) * STEP_MIN)
    high_r = int(math.ceil(high / STEP_MIN) * STEP_MIN)
    return (low_r, max(high_r, low_r + STEP_MIN))


def backtest(history: Sequence[PastVisit], test_share: float = 0.2) -> Backtest | None:
    split = int(len(history) * (1 - test_share))
    train, test = list(history[:split]), list(history[split:])
    hits = 0
    errors: list[float] = []
    for visit in test:
        for elapsed in EVAL_ELAPSED:
            if visit.minutes <= elapsed:
                continue
            predicted = remaining_range(train, elapsed, visit.party_size, visit.hour)
            if predicted is None:
                continue
            actual = visit.minutes - elapsed
            hits += predicted[0] <= actual <= predicted[1]
            errors.append(abs((predicted[0] + predicted[1]) / 2 - actual))
    if not errors:
        return None
    return Backtest(predictions=len(errors), coverage=hits / len(errors), mae_minutes=sum(errors) / len(errors))
