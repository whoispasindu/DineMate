import argparse
import math
import random
from datetime import datetime, time, timedelta

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app import models
from app.core import clock
from app.core.db import get_engine
from app.services.timeutil import at_local, local_date

STEP = timedelta(minutes=5)
DAY_START = time(7, 0)
DAY_END = time(20, 0)
PEAKS = ((8.25, 0.6, 0.35), (12.75, 0.9, 0.78), (19.0, 0.8, 0.4))
WEEKEND_SCALE = 0.4


def busy_fraction(hours: float, weekday: int, zone_bias: float) -> float:
    base = 0.08 + sum(height * math.exp(-(((hours - centre) / width) ** 2)) for centre, width, height in PEAKS)
    scale = WEEKEND_SCALE if weekday >= 5 else 1.0
    return min(0.98, base * scale * zone_bias)


def simulator_zones(session: Session) -> list[tuple[models.SeatingZone, str]]:
    devices = {d.id: d for d in session.scalars(select(models.Device).where(models.Device.kind == "simulator"))}
    result = []
    for layout in session.scalars(select(models.ZoneLayout).where(models.ZoneLayout.is_current)):
        if layout.device_id not in devices:
            continue
        for polygon in layout.polygons:
            if polygon.get("type") == "seating" and polygon.get("zone_id"):
                zone = session.get(models.SeatingZone, polygon["zone_id"])
                if zone is not None:
                    result.append((zone, layout.device_id))
    return result


def generate(session: Session, now: datetime, days: int, seed: int = 11) -> int:
    rng = random.Random(seed)
    today = local_date(now)
    first = at_local(today - timedelta(days=days), DAY_START)
    cutoff = at_local(today, time.min)
    rows = []
    for zone, device_id in simulator_zones(session):
        session.execute(
            delete(models.OccupancyReading).where(
                models.OccupancyReading.zone_id == zone.id,
                models.OccupancyReading.is_simulated,
                models.OccupancyReading.captured_at >= first,
                models.OccupancyReading.captured_at < cutoff,
            )
        )
        bias = 0.85 + rng.random() * 0.3
        for offset in range(days, 0, -1):
            day = today - timedelta(days=offset)
            t, end = at_local(day, DAY_START), at_local(day, DAY_END)
            while t < end:
                hours = (t - at_local(day, time.min)).total_seconds() / 3600
                occupied = round(zone.capacity * busy_fraction(hours, day.weekday(), bias) + rng.gauss(0, 1.5))
                occupied = max(0, min(zone.capacity, occupied))
                spread = max(1, round(zone.capacity * 0.06))
                rows.append(
                    {
                        "zone_id": zone.id,
                        "device_id": device_id,
                        "captured_at": t,
                        "received_at": t,
                        "estimated_occupied": occupied,
                        "occupied_low": max(0, occupied - spread),
                        "occupied_high": min(zone.capacity, occupied + spread),
                        "capacity_snapshot": zone.capacity,
                        "confidence": "medium",
                        "is_simulated": True,
                    }
                )
                t += STEP
    if rows:
        session.execute(insert(models.OccupancyReading), rows)
    session.commit()
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Add past days of SIMULATED occupancy for simulator zones so the forecast has history. "
        "Rows are stored with is_simulated=true; re-running replaces them."
    )
    parser.add_argument("--days", type=int, default=21)
    args = parser.parse_args(argv)
    with Session(get_engine()) as session:
        count = generate(session, clock.now(), args.days)
    print(f"Added {count} simulated readings over the past {args.days} days (labelled is_simulated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
