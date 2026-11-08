import random

from app.business.estimate import MIN_POOL, PastVisit, backtest, party_bucket, remaining_range


def history(n: int = 200, seed: int = 4) -> list[PastVisit]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        party = rng.choice([1, 2, 2, 3, 4, 6])
        base = 25 if party <= 2 else 40 if party <= 4 else 60
        out.append(PastVisit(hour=rng.choice([12, 13, 14, 18]), minutes=max(5.0, rng.gauss(base, 8)), party_size=party))
    return out


def test_party_buckets() -> None:
    assert [party_bucket(n) for n in (1, 2, 3, 4, 5, 9)] == [0, 0, 1, 1, 2, 2]


def test_no_estimate_without_enough_history() -> None:
    few = history(MIN_POOL - 1)
    assert remaining_range(few, 10, 2, 13) is None


def test_range_shrinks_as_time_passes_and_is_rounded_to_five() -> None:
    data = history()
    early = remaining_range(data, 5, 2, 13)
    late = remaining_range(data, 20, 2, 13)
    assert early is not None and late is not None
    assert all(v % 5 == 0 for v in (*early, *late))
    assert late[1] < early[1]
    assert early[1] > early[0]


def test_bigger_parties_stay_longer() -> None:
    data = history()
    small = remaining_range(data, 5, 2, 13)
    large = remaining_range(data, 5, 6, 13)
    assert small is not None and large is not None
    assert large[0] > small[0]


def test_plates_left_means_it_could_be_any_minute() -> None:
    result = remaining_range(history(), 10, 3, 13, plates_left=True)
    assert result is not None and result[0] == 0


def test_long_stays_beyond_history_say_any_minute() -> None:
    assert remaining_range(history(), 200, 2, 13) == (0, 5)


def test_backtest_reports_coverage_and_error() -> None:
    result = backtest(history(400))
    assert result is not None
    assert result.predictions > 50
    assert 0.3 < result.coverage < 0.8
    assert result.mae_minutes < 15
