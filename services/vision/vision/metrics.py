from dataclasses import dataclass
from statistics import mean

LEVEL_LIMITS = ((95.0, "near_capacity"), (80.0, "crowded"), (60.0, "busy"))


@dataclass(frozen=True)
class Sample:
    video: str
    t_seconds: float
    zone: str
    truth: int
    estimate: int
    low: int
    high: int
    capacity: int


@dataclass(frozen=True)
class Summary:
    label: str
    samples: int
    mae: float
    bias: float
    within_2: float
    coverage: float
    level_accuracy: float


def level_for(count: int, capacity: int) -> str:
    percent = count / capacity * 100 if capacity else 0.0
    return next((name for limit, name in LEVEL_LIMITS if percent >= limit), "normal")


def summarize(label: str, samples: list[Sample]) -> Summary:
    if not samples:
        return Summary(label, 0, 0.0, 0.0, 0.0, 0.0, 0.0)
    errors = [s.estimate - s.truth for s in samples]
    return Summary(
        label=label,
        samples=len(samples),
        mae=mean(abs(e) for e in errors),
        bias=mean(errors),
        within_2=sum(abs(e) <= 2 for e in errors) / len(samples),
        coverage=sum(s.low <= s.truth <= s.high for s in samples) / len(samples),
        level_accuracy=sum(level_for(s.estimate, s.capacity) == level_for(s.truth, s.capacity) for s in samples)
        / len(samples),
    )


def table(summaries: list[Summary]) -> str:
    header = f"{'':<28} {'n':>4} {'MAE':>6} {'bias':>6} {'±2':>6} {'in range':>9} {'level ok':>9}"
    rows = [header, "-" * len(header)]
    for s in summaries:
        rows.append(
            f"{s.label[:28]:<28} {s.samples:>4} {s.mae:>6.2f} {s.bias:>+6.2f} "
            f"{s.within_2:>6.0%} {s.coverage:>9.0%} {s.level_accuracy:>9.0%}"
        )
    return "\n".join(rows)


SEAT_STATES = ("free", "occupied", "held", "unknown")
TRUTH_STATES = ("free", "occupied", "held")


@dataclass(frozen=True)
class SeatSample:
    video: str
    t_seconds: float
    seat: str
    truth: str
    estimate: str


@dataclass(frozen=True)
class SeatSummary:
    label: str
    samples: int
    accuracy: float
    false_free: float
    hidden: float
    per_state: dict[str, float | None]


def summarize_seats(label: str, samples: list[SeatSample]) -> SeatSummary:
    if not samples:
        return SeatSummary(label, 0, 0.0, 0.0, 0.0, {s: None for s in TRUTH_STATES})
    per_state: dict[str, float | None] = {}
    for state in TRUTH_STATES:
        truth = [s for s in samples if s.truth == state]
        per_state[state] = sum(s.estimate == state for s in truth) / len(truth) if truth else None
    return SeatSummary(
        label=label,
        samples=len(samples),
        accuracy=sum(s.estimate == s.truth for s in samples) / len(samples),
        false_free=sum(s.estimate == "free" and s.truth != "free" for s in samples) / len(samples),
        hidden=sum(s.estimate == "unknown" for s in samples) / len(samples),
        per_state=per_state,
    )


def seat_table(summaries: list[SeatSummary]) -> str:
    header = f"{'':<28} {'n':>4} {'right':>6} {'false free':>11} {'hidden':>7} " + " ".join(
        f"{s:>9}" for s in TRUTH_STATES
    )
    rows = [header, "-" * len(header)]
    for s in summaries:
        states = " ".join(f"{'—' if v is None else f'{v:.0%}':>9}" for v in s.per_state.values())
        rows.append(
            f"{s.label[:28]:<28} {s.samples:>4} {s.accuracy:>6.0%} {s.false_free:>11.0%} {s.hidden:>7.0%} {states}"
        )
    return "\n".join(rows)


def confusion(samples: list[SeatSample]) -> str:
    header = f"{'hand count vs DineMate':<22}" + "".join(f"{s:>10}" for s in SEAT_STATES)
    rows = [header]
    for truth in TRUTH_STATES:
        counts = [sum(1 for s in samples if s.truth == truth and s.estimate == e) for e in SEAT_STATES]
        rows.append(f"{truth:<22}" + "".join(f"{c:>10}" for c in counts))
    return "\n".join(rows)
