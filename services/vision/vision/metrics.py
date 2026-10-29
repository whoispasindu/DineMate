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
