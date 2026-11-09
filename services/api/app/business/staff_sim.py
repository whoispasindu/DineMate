import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.business.sim import HOURLY

STEP = timedelta(minutes=1)
SWITCH_PER_MIN = 0.03
BREAK_PER_MIN = 0.004
ORDER_PER_MIN = 1.6
QUEUE_SCALE = 4.0

ROLE_AREAS: dict[str, tuple[tuple[str, float], ...]] = {
    "Barista": (("counter", 0.7), ("kitchen", 0.1), ("floor", 0.2)),
    "Cashier": (("counter", 0.9), ("floor", 0.1)),
    "Kitchen": (("kitchen", 0.85), ("counter", 0.15)),
    "Floor": (("floor", 0.8), ("counter", 0.2)),
}

MENU: tuple[tuple[str, Decimal], ...] = (
    ("Latte", Decimal(650)),
    ("Black coffee", Decimal(450)),
    ("Cappuccino", Decimal(700)),
    ("Iced coffee", Decimal(750)),
    ("Tea", Decimal(300)),
    ("Croissant", Decimal(400)),
    ("Sandwich", Decimal(850)),
    ("Cake slice", Decimal(550)),
)


@dataclass(frozen=True)
class SimWorker:
    staff_id: str
    role: str
    shift: tuple[int, int]
    till_code: str | None = None


@dataclass(frozen=True)
class SimPresence:
    staff_id: str
    area: str
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True)
class SimOrder:
    order_ref: str
    at: datetime
    cashier: str | None
    lines: tuple[tuple[str, int, Decimal], ...]


@dataclass
class WorkerRun:
    area: str | None = None
    since: datetime | None = None
    break_until: datetime | None = None


@dataclass
class StaffSim:
    workers: list[SimWorker]
    tz: ZoneInfo
    rng: random.Random
    runs: dict[str, WorkerRun] = field(default_factory=dict)
    closed: list[SimPresence] = field(default_factory=list)
    orders: list[SimOrder] = field(default_factory=list)
    reported: int = 0

    def __post_init__(self) -> None:
        self.runs = {w.staff_id: WorkerRun() for w in self.workers}

    def _pick(self, role: str) -> str:
        areas = ROLE_AREAS.get(role, (("floor", 1.0),))
        return self.rng.choices([a for a, _ in areas], weights=[w for _, w in areas])[0]

    def _close(self, worker: SimWorker, run: WorkerRun, at: datetime) -> None:
        if run.area is not None and run.since is not None and at > run.since:
            self.closed.append(SimPresence(worker.staff_id, run.area, run.since, at))
        run.area, run.since = None, None

    def step(self, now: datetime) -> None:
        local = now.astimezone(self.tz)
        for worker in self.workers:
            run = self.runs[worker.staff_id]
            on_shift = worker.shift[0] <= local.hour < worker.shift[1]
            resting = run.break_until is not None and now < run.break_until
            if not on_shift or resting:
                self._close(worker, run, now)
                continue
            if run.area is None:
                run.area, run.since = self._pick(worker.role), now
            elif self.rng.random() < BREAK_PER_MIN:
                self._close(worker, run, now)
                run.break_until = now + timedelta(minutes=self.rng.uniform(5, 15))
            elif self.rng.random() < SWITCH_PER_MIN:
                area = self._pick(worker.role)
                if area != run.area:
                    self._close(worker, run, now)
                    run.area, run.since = area, now

    def _sell(self, now: datetime) -> None:
        local = now.astimezone(self.tz)
        chance = ORDER_PER_MIN * HOURLY.get(local.hour, 0.0) / 2
        if self.rng.random() >= chance:
            return
        at_counter = [w for w in self.workers if w.till_code and self.runs[w.staff_id].area == "counter"]
        cashier = self.rng.choice(at_counter).till_code if at_counter else None
        lines = tuple(
            (name, self.rng.choice((1, 1, 1, 2)), price)
            for name, price in self.rng.sample(MENU, self.rng.choice((1, 1, 2, 2, 3)))
        )
        self.orders.append(SimOrder(f"S{local:%y%m%d%H%M}{len(self.orders) % 1000:03d}", now, cashier, lines))

    def run_until(self, start: datetime, end: datetime, sell: bool = True) -> None:
        at = start
        while at <= end:
            self.step(at)
            if sell:
                self._sell(at)
            at += STEP

    def presence(self) -> list[SimPresence]:
        open_rows = [
            SimPresence(sid, run.area, run.since, None)
            for sid, run in self.runs.items()
            if run.area is not None and run.since is not None
        ]
        return [*self.closed, *open_rows]

    def drain(self) -> list[SimPresence]:
        fresh = self.closed[self.reported :]
        self.reported = len(self.closed)
        open_rows = [
            SimPresence(sid, run.area, run.since, None)
            for sid, run in self.runs.items()
            if run.area is not None and run.since is not None
        ]
        return [*fresh, *open_rows]


def queue_people(local: datetime, rng: random.Random) -> int:
    return max(0, round(rng.gauss(HOURLY.get(local.hour, 0.0) * QUEUE_SCALE, 1.5)))
