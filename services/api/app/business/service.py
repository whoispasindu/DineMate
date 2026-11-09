import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.business import schemas as s
from app.business.estimate import PastVisit, remaining_range
from app.business.models import QueueReading, StaffMember, StaffPresence, TableVisit, VenueTable
from app.business.tables import SeatView, TableView, table_state
from app.business.visits import OpenVisit, step
from app.core.errors import ApiError
from app.routers.devices import current_layout

HISTORY_DAYS = 28
OFFLINE_AFTER = timedelta(minutes=2)
QUEUE_FRESH = timedelta(minutes=2)
SeatKey = tuple[uuid.UUID, str]


def tz_of(venue: models.Canteen) -> ZoneInfo:
    return ZoneInfo(venue.timezone)


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0), tzinfo=tz)
    return start, start + timedelta(days=1)


def minutes(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60


def avg_min(values: list[float]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def venue_tables(session: Session, venue_id: str) -> list[VenueTable]:
    return list(
        session.scalars(select(VenueTable).where(VenueTable.venue_id == venue_id).order_by(VenueTable.sort_order))
    )


def seat_views(session: Session, zone_ids: set[uuid.UUID]) -> dict[SeatKey, SeatView]:
    if not zone_ids:
        return {}
    rows = session.scalars(select(models.SeatState).where(models.SeatState.zone_id.in_(zone_ids)))
    return {
        (r.zone_id, r.seat_id): SeatView(state=r.state, since=r.since, free_soon=r.free_soon, updated_at=r.updated_at)
        for r in rows
    }


def views_for(tables: list[VenueTable], seats: dict[SeatKey, SeatView], now: datetime) -> dict[uuid.UUID, TableView]:
    return {
        t.id: table_state(
            [seats[(t.zone_id, sid)] for sid in t.seat_ids if (t.zone_id, sid) in seats], now, t.cleared_at
        )
        for t in tables
    }


def open_visits(session: Session, table_ids: list[uuid.UUID]) -> dict[uuid.UUID, TableVisit]:
    rows = session.scalars(select(TableVisit).where(TableVisit.table_id.in_(table_ids), TableVisit.ended_at.is_(None)))
    return {v.table_id: v for v in rows}


def update_tables(session: Session, zone_ids: set[uuid.UUID], now: datetime, simulated: bool) -> int:
    tables = list(session.scalars(select(VenueTable).where(VenueTable.zone_id.in_(zone_ids))))
    if not tables:
        return 0
    views = views_for(tables, seat_views(session, {t.zone_id for t in tables}), now)
    opened = open_visits(session, [t.id for t in tables])
    changes = 0
    for table in tables:
        current = opened.get(table.id)
        previous = OpenVisit(current.started_at, current.last_seen_at, current.party_size) if current else None
        result = step(previous, views[table.id], now)
        if result.kind == "start":
            session.add(
                TableVisit(
                    table_id=table.id,
                    started_at=result.started_at,
                    last_seen_at=result.last_seen_at,
                    party_size=result.party_size,
                    is_simulated=simulated,
                )
            )
        elif result.kind == "extend" and current is not None:
            current.last_seen_at = result.last_seen_at or now
            current.party_size = result.party_size
        elif result.kind == "end" and current is not None:
            current.ended_at = result.ended_at
        changes += result.kind != "none"
    return changes


def finished_visits(session: Session, venue_id: str, since: datetime) -> list[tuple[TableVisit, VenueTable]]:
    rows = session.execute(
        select(TableVisit, VenueTable)
        .join(VenueTable, VenueTable.id == TableVisit.table_id)
        .where(VenueTable.venue_id == venue_id, TableVisit.started_at >= since)
        .order_by(TableVisit.started_at)
    )
    return [(v, t) for v, t in rows]


def past_visits(session: Session, venue: models.Canteen, now: datetime) -> list[PastVisit]:
    tz = tz_of(venue)
    return [
        PastVisit(
            hour=v.started_at.astimezone(tz).hour, minutes=minutes(v.started_at, v.ended_at), party_size=v.party_size
        )
        for v, _ in finished_visits(session, venue.id, now - timedelta(days=HISTORY_DAYS))
        if v.ended_at is not None
    ]


def floor_table(
    table: VenueTable, zone_name: str, view: TableView, history: list[PastVisit], now: datetime, tz: ZoneInfo
) -> s.FloorTable:
    seated = round(minutes(view.since, now)) if view.state == "occupied" and view.since else None
    estimate = None
    if seated is not None:
        found = remaining_range(history, seated, view.party_size, now.astimezone(tz).hour, view.plates_left)
        estimate = s.LeaveEstimate(low_min=found[0], high_min=found[1]) if found else None
    return s.FloorTable(
        id=str(table.id),
        name=table.name,
        zone_id=str(table.zone_id),
        zone_name=zone_name,
        shape=table.shape,  # type: ignore[arg-type]
        x=table.x,
        y=table.y,
        w=table.w,
        h=table.h,
        seats=len(table.seat_ids),
        state=view.state,
        party_size=view.party_size,
        since=view.since,
        seated_min=seated,
        plates_left=view.plates_left,
        estimate=estimate,
    )


def zone_names(venue: models.Canteen) -> dict[uuid.UUID, str]:
    return {z.id: z.name for z in venue.zones}


def counter_now(session: Session, venue_id: str, now: datetime) -> tuple[int | None, int | None]:
    staff_ids = select(StaffMember.id).where(StaffMember.venue_id == venue_id)
    has_staff = session.scalar(select(func.count()).select_from(StaffMember).where(StaffMember.venue_id == venue_id))
    if not has_staff:
        return None, None
    on_counter = session.scalar(
        select(func.count(func.distinct(StaffPresence.staff_id))).where(
            StaffPresence.staff_id.in_(staff_ids), StaffPresence.area == "counter", StaffPresence.ended_at.is_(None)
        )
    )
    reading = session.scalar(
        select(QueueReading)
        .where(QueueReading.venue_id == venue_id, QueueReading.at >= now - QUEUE_FRESH)
        .order_by(QueueReading.at.desc())
        .limit(1)
    )
    return int(on_counter or 0), reading.people if reading else None


def floor(session: Session, venue: models.Canteen, now: datetime) -> s.VenueFloor:
    tz = tz_of(venue)
    tables = venue_tables(session, venue.id)
    seats = seat_views(session, {t.zone_id for t in tables})
    views = views_for(tables, seats, now)
    history = past_visits(session, venue, now)
    names = zone_names(venue)
    items = [floor_table(t, names.get(t.zone_id, ""), views[t.id], history, now, tz) for t in tables]
    start, _ = day_bounds(now.astimezone(tz).date(), tz)
    today = [v for v, _ in finished_visits(session, venue.id, start)]
    stays = [minutes(v.started_at, v.ended_at) for v in today if v.ended_at is not None]
    counter_staff, queue_people = counter_now(session, venue.id, now)
    totals = s.FloorTotals(
        tables=len(items),
        free=sum(1 for t in items if t.state == "free"),
        guests_seated=sum(t.party_size for t in items),
        visits_today=len(today),
        avg_stay_today_min=avg_min(stays),
        turns_today=round(len(today) / len(items), 1) if items else 0.0,
        counter_staff=counter_staff,
        queue_people=queue_people,
    )
    updated = max((seat.updated_at for seat in seats.values()), default=None)
    return s.VenueFloor(
        server_time=now,
        venue_id=venue.id,
        venue_name=venue.name,
        is_sample=venue.is_sample,
        updated_at=updated,
        totals=totals,
        tables=items,
    )


def _visits_between(
    session: Session, venue_id: str, start: datetime, end: datetime
) -> list[tuple[TableVisit, VenueTable]]:
    return [(v, t) for v, t in finished_visits(session, venue_id, start) if v.started_at < end]


def customers(session: Session, venue: models.Canteen, day: date, now: datetime) -> s.CustomerDay:
    tz = tz_of(venue)
    start, end = day_bounds(day, tz)
    rows = _visits_between(session, venue.id, start, end)
    cutoff = min(end, now)
    last_week = _visits_between(session, venue.id, start - timedelta(days=7), cutoff - timedelta(days=7))
    stays = [minutes(v.started_at, v.ended_at) for v, _ in rows if v.ended_at is not None]
    hours = Counter(v.started_at.astimezone(tz).hour for v, _ in rows)
    tables = venue_tables(session, venue.id)
    by_table: dict[uuid.UUID, list[float]] = defaultdict(list)
    turns: Counter[uuid.UUID] = Counter()
    for v, t in rows:
        turns[t.id] += 1
        if v.ended_at is not None:
            by_table[t.id].append(minutes(v.started_at, v.ended_at))
    return s.CustomerDay(
        server_time=now,
        venue_id=venue.id,
        day=day,
        is_sample=venue.is_sample,
        visits=len(rows),
        visits_last_week=len(last_week),
        guests=sum(v.party_size for v, _ in rows),
        avg_stay_min=avg_min(stays),
        median_stay_min=round(median(stays)) if stays else None,
        turns_per_table=round(len(rows) / len(tables), 1) if tables else 0.0,
        by_hour=[s.HourCount(hour=h, visits=hours.get(h, 0)) for h in range(24)],
        by_table=[
            s.TableStay(
                table_id=str(t.id),
                name=t.name,
                seats=len(t.seat_ids),
                avg_stay_min=avg_min(by_table[t.id]),
                turns=turns[t.id],
            )
            for t in tables
        ],
    )


def report(session: Session, venue: models.Canteen, span: str, now: datetime) -> s.VenueReport:
    tz = tz_of(venue)
    today = now.astimezone(tz).date()
    count = 1 if span == "day" else 7
    days = []
    for offset in range(count - 1, -1, -1):
        day = today - timedelta(days=offset)
        start, end = day_bounds(day, tz)
        rows = _visits_between(session, venue.id, start, end)
        stays = [minutes(v.started_at, v.ended_at) for v, _ in rows if v.ended_at is not None]
        days.append(
            s.DayTotal(
                day=day, visits=len(rows), guests=sum(v.party_size for v, _ in rows), avg_stay_min=avg_min(stays)
            )
        )
    heat_start, _ = day_bounds(today - timedelta(days=HISTORY_DAYS - 1), tz)
    cells = Counter(
        (local.weekday(), local.hour)
        for local in (v.started_at.astimezone(tz) for v, _ in finished_visits(session, venue.id, heat_start))
    )
    return s.VenueReport(
        server_time=now,
        venue_id=venue.id,
        range=span,  # type: ignore[arg-type]
        is_sample=venue.is_sample,
        days=days,
        heat=[s.HeatCell(weekday=wd, hour=h, visits=n) for (wd, h), n in sorted(cells.items())],
        heat_days=HISTORY_DAYS,
    )


def cameras(session: Session, venue: models.Canteen, now: datetime) -> s.VenueCameras:
    names = zone_names(venue)
    items = []
    for device in session.scalars(
        select(models.Device).where(models.Device.canteen_id == venue.id).order_by(models.Device.id)
    ):
        last_snapshot = session.scalar(
            select(models.ZoneSeatStatus.captured_at)
            .where(models.ZoneSeatStatus.device_id == device.id)
            .order_by(models.ZoneSeatStatus.captured_at.desc())
            .limit(1)
        )
        beat = session.scalar(
            select(models.DeviceHeartbeat)
            .where(models.DeviceHeartbeat.device_id == device.id)
            .order_by(models.DeviceHeartbeat.received_at.desc())
            .limit(1)
        )
        seen = device.last_heartbeat_at
        if seen is None or now - seen > OFFLINE_AFTER or not device.is_enabled:
            status = "offline"
        elif last_snapshot is None or now - last_snapshot > OFFLINE_AFTER:
            status = "not_reporting"
        else:
            status = "ok"
        layout = current_layout(session, device.id)
        zones = [
            names.get(uuid.UUID(str(p["zone_id"])), "")
            for p in (layout.polygons if layout else [])
            if p.get("type") == "seating" and p.get("zone_id")
        ]
        items.append(
            s.CameraHealth(
                id=device.id,
                kind=device.kind,  # type: ignore[arg-type]
                zones=[z for z in zones if z],
                status=status,  # type: ignore[arg-type]
                fps=beat.fps if beat else None,
                last_seen_at=seen,
            )
        )
    return s.VenueCameras(server_time=now, venue_id=venue.id, items=items)


def layout_seats(session: Session, venue: models.Canteen) -> dict[uuid.UUID, list[s.SeatPoint]]:
    seats: dict[uuid.UUID, list[s.SeatPoint]] = defaultdict(list)
    for device in session.scalars(select(models.Device).where(models.Device.canteen_id == venue.id)):
        layout = current_layout(session, device.id)
        for polygon in layout.polygons if layout else []:
            if polygon.get("type") != "seating" or not polygon.get("zone_id"):
                continue
            zone_id = uuid.UUID(str(polygon["zone_id"]))
            seats[zone_id].extend(
                s.SeatPoint(seat_id=str(p["seat_id"]), x=float(p["x"]), y=float(p["y"]))
                for p in polygon.get("seats", [])
            )
    return seats


def table_out(t: VenueTable) -> s.TableOut:
    return s.TableOut(
        id=str(t.id),
        name=t.name,
        zone_id=str(t.zone_id),
        shape=t.shape,
        x=t.x,
        y=t.y,
        w=t.w,
        h=t.h,
        seat_ids=list(t.seat_ids),  # type: ignore[arg-type]
    )


def table_layout(session: Session, venue: models.Canteen, now: datetime) -> s.TableLayout:
    seats = layout_seats(session, venue)
    zones = [
        s.LayoutZoneSeats(zone_id=str(z.id), name=z.name, seats=seats.get(z.id, [])) for z in venue.zones if z.is_active
    ]
    return s.TableLayout(
        server_time=now, venue_id=venue.id, zones=zones, tables=[table_out(t) for t in venue_tables(session, venue.id)]
    )


def _invalid(message: str, **details: Any) -> ApiError:
    return ApiError(422, "validation_error", message, details)


def replace_tables(
    session: Session, venue: models.Canteen, payload: s.TablesIn
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seats = {zone_id: {p.seat_id for p in points} for zone_id, points in layout_seats(session, venue).items()}
    zone_ids = {str(z.id) for z in venue.zones}
    names = [t.name.strip() for t in payload.tables]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise _invalid("Table names must be unique.", names=duplicates)
    used: dict[tuple[str, str], str] = {}
    for table in payload.tables:
        if table.zone_id not in zone_ids:
            raise _invalid("Zone is not in this venue.", zone_id=table.zone_id)
        if table.x + table.w > 1 or table.y + table.h > 1:
            raise _invalid("Tables must sit inside the floor plan.", name=table.name)
        known = seats.get(uuid.UUID(table.zone_id), set())
        stray = sorted(set(table.seat_ids) - known)
        if stray:
            raise _invalid("Seats are not in this zone's camera layout.", seat_ids=stray)
        for seat_id in table.seat_ids:
            key = (table.zone_id, seat_id)
            if key in used:
                raise _invalid("A seat can only belong to one table.", seat_id=seat_id, tables=[used[key], table.name])
            used[key] = table.name
    existing = {str(t.id): t for t in venue_tables(session, venue.id)}
    before = [table_out(t).model_dump() for t in existing.values()]
    keep: set[str] = set()
    for order, table in enumerate(payload.tables):
        row = existing.get(table.id or "")
        if row is None:
            row = VenueTable(venue_id=venue.id)
            session.add(row)
        else:
            keep.add(str(row.id))
        row.zone_id = uuid.UUID(table.zone_id)
        row.name = table.name.strip()
        row.shape = table.shape
        row.x, row.y, row.w, row.h = table.x, table.y, table.w, table.h
        row.seat_ids = list(dict.fromkeys(table.seat_ids))
        row.sort_order = order
    removed = [uuid.UUID(i) for i in existing if i not in keep]
    if removed:
        session.execute(delete(VenueTable).where(VenueTable.id.in_(removed)))
    session.flush()
    after = [table_out(t).model_dump() for t in venue_tables(session, venue.id)]
    return before, after


def load_venue_table(session: Session, table_id: str) -> VenueTable | None:
    try:
        return session.get(VenueTable, uuid.UUID(table_id))
    except ValueError:
        return None


def org_venues(session: Session, organization_id: str) -> list[models.Canteen]:
    return list(
        session.scalars(
            select(models.Canteen)
            .options(selectinload(models.Canteen.zones))
            .where(models.Canteen.organization_id == organization_id, models.Canteen.kind == models.VENUE)
            .order_by(models.Canteen.sort_order, models.Canteen.name)
        )
    )


def purge_expired(session: Session, now: datetime) -> int:
    removed = 0
    for org in session.scalars(select(models.Organization).where(models.Organization.kind == "business")):
        cutoff = now - timedelta(days=org.retention_days)
        venue_ids = select(models.Canteen.id).where(models.Canteen.organization_id == org.id)
        table_ids = select(VenueTable.id).where(VenueTable.venue_id.in_(venue_ids))
        result = session.execute(
            delete(TableVisit).where(TableVisit.table_id.in_(table_ids), TableVisit.ended_at < cutoff)
        )
        removed += result.rowcount or 0  # type: ignore[attr-defined]
    return removed
