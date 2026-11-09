import random
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app import models
from app.business.models import QueueReading, StaffMember, StaffPresence, TableVisit, TillItem, TillOrder, VenueTable
from app.business.service import update_tables
from app.business.sim import CafeSim, SimTable, zone_summaries
from app.business.staff_sim import SimWorker, StaffSim, queue_people
from app.core.config import get_settings
from app.core.device_auth import hash_token

ORG_ID = "sample-cafe-group"
VENUE_ID = "v-sample-cafe"
DEVICE_ID = "sim-cafe"
HISTORY_DAYS = 28
STAFF_DAYS = 14
ORDER_DAYS = 7
QUEUE_DAYS = 3

STAFF = [
    ("Barista 1", "Barista", "face", None, "B1", (7, 15)),
    ("Barista 2", "Barista", "face", None, "B2", (11, 20)),
    ("Cashier 1", "Cashier", "badge", 11, "C1", (8, 16)),
    ("Kitchen 1", "Kitchen", "face", None, None, (7, 15)),
    ("Floor 1", "Floor", "badge", 12, None, (11, 21)),
]
SEED = 20261120


@dataclass(frozen=True)
class TableSeed:
    name: str
    zone: str
    shape: str
    box: tuple[float, float, float, float]
    seats: int


ZONES = {
    "Window side": [[0.02, 0.03], [0.5, 0.03], [0.5, 0.29], [0.25, 0.29], [0.25, 0.75], [0.02, 0.75]],
    "Main floor": [[0.25, 0.29], [0.95, 0.29], [0.95, 0.97], [0.25, 0.97]],
}

TABLES = [
    TableSeed("T1", "Window side", "round", (0.04, 0.06, 0.11, 0.15), 2),
    TableSeed("T2", "Window side", "round", (0.19, 0.06, 0.11, 0.15), 2),
    TableSeed("T3", "Window side", "rect", (0.34, 0.06, 0.13, 0.15), 2),
    TableSeed("T4", "Window side", "rect", (0.04, 0.32, 0.19, 0.16), 4),
    TableSeed("T5", "Main floor", "rect", (0.27, 0.32, 0.19, 0.16), 4),
    TableSeed("T6", "Window side", "rect", (0.04, 0.55, 0.19, 0.16), 4),
    TableSeed("T7", "Main floor", "rect", (0.27, 0.55, 0.19, 0.16), 4),
    TableSeed("T8", "Main floor", "rect", (0.54, 0.32, 0.19, 0.16), 4),
    TableSeed("T9", "Main floor", "rect", (0.54, 0.55, 0.19, 0.16), 4),
    TableSeed("T10", "Main floor", "round", (0.78, 0.32, 0.11, 0.15), 2),
    TableSeed("T11", "Main floor", "round", (0.78, 0.55, 0.11, 0.15), 2),
    TableSeed("T12", "Main floor", "rect", (0.54, 0.78, 0.35, 0.16), 6),
]


def seat_points(table: TableSeed) -> list[dict[str, object]]:
    x, y, w, h = table.box
    top = (table.seats + 1) // 2
    bottom = table.seats - top
    points = []
    for i in range(top):
        points.append(
            {"seat_id": f"{table.name}-{i + 1}", "x": round(x + w * (i + 1) / (top + 1), 4), "y": round(y + h * 0.3, 4)}
        )
    for i in range(bottom):
        points.append(
            {
                "seat_id": f"{table.name}-{top + i + 1}",
                "x": round(x + w * (i + 1) / (bottom + 1), 4),
                "y": round(y + h * 0.7, 4),
            }
        )
    return points


def _seed_place(session: Session) -> tuple[dict[str, uuid.UUID], list[VenueTable]]:
    session.add(models.Organization(id=ORG_ID, name="Sample Café Group", kind="business", is_sample=True))
    session.flush()
    session.add(
        models.Canteen(
            id=VENUE_ID, name="Sample Café", organization_id=ORG_ID, kind=models.VENUE, sort_order=0, is_sample=True
        )
    )
    session.add_all(
        models.CanteenHours(canteen_id=VENUE_ID, weekday=wd, opens=time(7), closes=time(21)) for wd in range(7)
    )
    session.flush()
    zone_ids: dict[str, uuid.UUID] = {}
    for order, name in enumerate(ZONES):
        capacity = sum(t.seats for t in TABLES if t.zone == name)
        zone = models.SeatingZone(
            canteen_id=VENUE_ID, name=name, capacity=capacity, sort_order=order, is_monitored=True
        )
        session.add(zone)
        session.flush()
        zone_ids[name] = zone.id
    session.add(
        models.Device(
            id=DEVICE_ID,
            canteen_id=VENUE_ID,
            kind="simulator",
            config={},
            token_hash=hash_token(get_settings().simulator_token),
        )
    )
    session.flush()
    polygons: list[dict[str, object]] = [
        {
            "type": "seating",
            "zone_id": str(zone_ids[name]),
            "points": points,
            "seats": [p for t in TABLES if t.zone == name for p in seat_points(t)],
        }
        for name, points in ZONES.items()
    ]
    session.add(models.ZoneLayout(device_id=DEVICE_ID, version=1, polygons=polygons, is_current=True))
    tables = []
    for order, t in enumerate(TABLES):
        x, y, w, h = t.box
        row = VenueTable(
            venue_id=VENUE_ID,
            zone_id=zone_ids[t.zone],
            name=t.name,
            shape=t.shape,
            x=x,
            y=y,
            w=w,
            h=h,
            seat_ids=[str(p["seat_id"]) for p in seat_points(t)],
            sort_order=order,
        )
        session.add(row)
        tables.append(row)
    session.flush()
    return zone_ids, tables


def _seed_activity(session: Session, tables: list[VenueTable], now: datetime) -> None:
    sim = CafeSim(
        [SimTable(t.name, str(t.zone_id), tuple(t.seat_ids)) for t in tables],
        ZoneInfo("Asia/Colombo"),
        random.Random(SEED),
    )
    start = now - timedelta(days=HISTORY_DAYS)
    sim.run_until(start.replace(second=0, microsecond=0), now)
    by_name = {t.name: t for t in tables}
    session.execute(
        insert(TableVisit),
        [
            {
                "table_id": by_name[v.table_id].id,
                "started_at": v.started_at,
                "last_seen_at": v.ended_at,
                "ended_at": v.ended_at,
                "party_size": v.party_size,
                "is_simulated": True,
            }
            for v in sim.visits
        ],
    )
    seats = sim.seats(now)
    for seat in seats:
        session.add(
            models.SeatState(
                zone_id=uuid.UUID(seat["zone_id"]),
                seat_id=seat["seat_id"],
                state=seat["state"],
                since=seat["since"],
                free_soon=seat["free_soon"],
                updated_at=now,
            )
        )
    for zone in zone_summaries(seats):
        session.add(
            models.ZoneSeatStatus(
                zone_id=uuid.UUID(zone["zone_id"]),
                device_id=DEVICE_ID,
                captured_at=now,
                free=zone["free"],
                occupied=zone["occupied"],
                held=zone["held"],
                unknown=zone["unknown"],
                free_soon=zone["free_soon"],
                is_simulated=True,
            )
        )
    session.flush()
    update_tables(session, {t.zone_id for t in tables}, now, simulated=True)


def _seed_staff(session: Session, now: datetime) -> None:
    tz = ZoneInfo("Asia/Colombo")
    members = []
    for name, role, method, badge, till, _ in STAFF:
        member = StaffMember(
            venue_id=VENUE_ID,
            display_name=name,
            role_label=role,
            method=method,
            badge_code=badge,
            till_code=till,
            consent_at=now - timedelta(days=18),
            consent_version="sample-notice-v1",
            is_sample=True,
            created_at=now - timedelta(days=20),
        )
        session.add(member)
        members.append(member)
    session.flush()
    workers = [
        SimWorker(str(m.id), role, shift, till) for m, (_, role, _, _, till, shift) in zip(members, STAFF, strict=True)
    ]
    sim = StaffSim(workers, tz, random.Random(SEED + 1))
    start = (now - timedelta(days=STAFF_DAYS)).replace(second=0, microsecond=0)
    sim.run_until(start, now)
    session.add_all(
        StaffPresence(
            staff_id=uuid.UUID(p.staff_id), area=p.area, started_at=p.started_at, ended_at=p.ended_at, is_simulated=True
        )
        for p in sim.presence()
    )
    codes = {w.till_code: uuid.UUID(w.staff_id) for w in workers if w.till_code}
    recent = [o for o in sim.orders if o.at >= now - timedelta(days=ORDER_DAYS)]
    ids = session.scalars(
        insert(TillOrder).returning(TillOrder.id, sort_by_parameter_order=True),
        [
            {
                "venue_id": VENUE_ID,
                "order_ref": order.order_ref,
                "at": order.at,
                "cashier_code": order.cashier,
                "staff_id": codes.get(order.cashier or ""),
                "total": sum((price * qty for _, qty, price in order.lines), start=0),
                "is_sample": True,
            }
            for order in recent
        ],
    ).all()
    session.execute(
        insert(TillItem),
        [
            {"order_id": order_id, "name": n, "qty": q, "unit_price": p}
            for order_id, order in zip(ids, recent, strict=True)
            for n, q, p in order.lines
        ],
    )
    rng = random.Random(SEED + 2)
    at = now - timedelta(days=QUEUE_DAYS)
    readings = []
    while at <= now:
        local = at.astimezone(tz)
        if 7 <= local.hour < 21:
            readings.append({"venue_id": VENUE_ID, "at": at, "people": queue_people(local, rng), "is_simulated": True})
        at += timedelta(minutes=1)
    if readings:
        session.execute(insert(QueueReading), readings)


def seed_sample_cafe(session: Session, now: datetime) -> bool:
    if session.get(models.Organization, ORG_ID) is not None:
        return False
    _, tables = _seed_place(session)
    _seed_activity(session, tables, now)
    _seed_staff(session, now)
    session.flush()
    return True
