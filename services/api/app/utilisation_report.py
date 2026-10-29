import argparse
from collections.abc import Callable
from datetime import datetime, time, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.core import clock
from app.core.db import get_engine
from app.services.forecast import SLOT
from app.services.history import time_bin
from app.services.timeutil import CAMPUS_TZ
from app.services.utilisation import EMPTY_SHARE, Utilisation, ZoneSlot, summarise


def load_slots(session: Session, start: datetime, end: datetime) -> tuple[list[ZoneSlot], bool]:
    r = models.OccupancyReading
    t = time_bin(SLOT).label("t")
    rows = session.execute(
        select(
            t, models.SeatingZone.canteen_id, r.zone_id, func.avg(r.estimated_occupied), func.max(r.capacity_snapshot)
        )
        .join(models.SeatingZone, models.SeatingZone.id == r.zone_id)
        .where(r.captured_at >= start, r.captured_at < end)
        .group_by(t, models.SeatingZone.canteen_id, r.zone_id)
    )
    slots = [ZoneSlot(cid, str(zid), at, float(occ), int(cap)) for at, cid, zid, occ, cap in rows]
    simulated = session.scalar(select(func.bool_or(r.is_simulated)).where(r.captured_at >= start, r.captured_at < end))
    return slots, bool(simulated)


def opening_check(session: Session) -> Callable[[str, datetime], bool]:
    hours: dict[tuple[str, int], list[tuple[time, time]]] = {}
    for h in session.scalars(select(models.CanteenHours)):
        hours.setdefault((h.canteen_id, h.weekday), []).append((h.opens, h.closes))

    def is_open(canteen_id: str, at: datetime) -> bool:
        local = at.astimezone(CAMPUS_TZ)
        return any(o <= local.time() < c for o, c in hours.get((canteen_id, local.weekday()), []))

    return is_open


def render(result: Utilisation, names: dict[str, str], days: int, simulated: bool, now: datetime) -> str:
    lines = [
        "# Seat utilisation and energy opportunity",
        "",
        f"Generated {now:%Y-%m-%d %H:%M} UTC by `python -m app.utilisation_report` over the last {days} days.",
        f"Data source: **{'includes simulated readings' if simulated else 'real readings only'}**. "
        "Only opening hours are counted. These are seating figures, not building occupancy.",
        "",
        "| Canteen | Seat-hours used | Seat-hours available | Utilisation | Empty-zone hours |",
        "|---|---|---|---|---|",
    ]
    for c in result.canteens:
        share = "—" if c.utilisation is None else f"{c.utilisation:.0%}"
        lines.append(
            f"| {names.get(c.canteen_id, c.canteen_id)} | {c.seat_hours_used:.0f} | {c.seat_hours_available:.0f} | "
            f"{share} | {c.empty_zone_hours:.1f} |"
        )
    balance = (
        "not enough canteens with data"
        if result.peak_cv is None
        else f"{result.peak_cv:.2f} (average over {result.peak_days} daily peaks; 0 = evenly spread)"
    )
    lines += [
        "",
        f"Utilisation balance at the daily peak (coefficient of variation across canteens): {balance}.",
        "",
        f"A zone counts as empty when about {EMPTY_SHARE:.0%} of its seats or fewer are in use (at least 1 seat).",
        "Empty-zone hours times the measured power of that zone's fans and lights gives the kWh at stake",
        "(plan 18.1). Measure one circuit with a smart plug, with facilities' permission, before claiming any saving.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seat-hours, utilisation balance and empty-zone hours per canteen.")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--out", type=Path, help="write the Markdown report to this file")
    args = parser.parse_args(argv)
    now = clock.now()
    with Session(get_engine()) as session:
        slots, simulated = load_slots(session, now - timedelta(days=args.days), now)
        result = summarise(slots, opening_check(session))
        names = {cid: name for cid, name in session.execute(select(models.Canteen.id, models.Canteen.name))}
    report = render(result, names, args.days, simulated, now)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
