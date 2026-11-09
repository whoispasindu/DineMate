import itertools
import random
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.business.staff_sim import SimWorker, StaffSim, queue_people

TZ = ZoneInfo("Asia/Colombo")
WORKERS = [
    SimWorker("b1", "Barista", (7, 15), "B1"),
    SimWorker("k1", "Kitchen", (7, 15)),
    SimWorker("f1", "Floor", (11, 21)),
]


def day() -> StaffSim:
    sim = StaffSim(WORKERS, TZ, random.Random(5))
    start = datetime(2026, 11, 19, 0, 0, tzinfo=TZ).astimezone(UTC)
    sim.run_until(start, start + timedelta(days=1))
    return sim


def test_presence_stays_inside_shifts_and_areas_do_not_overlap_per_worker() -> None:
    sim = day()
    shifts = {w.staff_id: w.shift for w in WORKERS}
    rows = sim.presence()
    assert rows
    for row in rows:
        assert row.area in ("counter", "kitchen", "floor")
        start, end = shifts[row.staff_id]
        assert start <= row.started_at.astimezone(TZ).hour < end
    for worker in WORKERS:
        mine = sorted((r for r in rows if r.staff_id == worker.staff_id and r.ended_at), key=lambda r: r.started_at)
        assert all(a.ended_at is not None and a.ended_at <= b.started_at for a, b in itertools.pairwise(mine))


def test_orders_go_to_cashiers_on_the_counter_or_nobody() -> None:
    sim = day()
    assert len(sim.orders) > 50
    assert {o.cashier for o in sim.orders} <= {"B1", None}
    assert all(o.lines for o in sim.orders)
    assert len({o.order_ref for o in sim.orders}) == len(sim.orders)


def test_drain_sends_new_closed_intervals_once_and_open_ones_every_time() -> None:
    sim = StaffSim(WORKERS, TZ, random.Random(9))
    lunch = datetime(2026, 11, 20, 12, 0, tzinfo=TZ).astimezone(UTC)
    sim.run_until(lunch - timedelta(hours=2), lunch, sell=False)
    first = sim.drain()
    second = sim.drain()
    assert all(r.ended_at is None for r in second)
    assert len(first) >= len(second)


def test_queue_is_longer_at_lunch_than_at_opening() -> None:
    rng = random.Random(2)
    lunch = sum(queue_people(datetime(2026, 11, 20, 12, 30, tzinfo=TZ), rng) for _ in range(50))
    early = sum(queue_people(datetime(2026, 11, 20, 7, 10, tzinfo=TZ), rng) for _ in range(50))
    assert lunch > early
