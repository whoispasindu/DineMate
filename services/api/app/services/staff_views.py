import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app import models, schemas
from app import schemas_staff as staff
from app.safety.models import SafetySource
from app.safety.service import public_status, source_online
from app.services.meal_status import meal_status
from app.services.occupancy import best_candidate
from app.services.rules import OFFLINE_AFTER, zone_devices
from app.services.timeutil import at_local, local, local_date, twelve_hour
from app.services.views import CanteenBundle, bundle_forecast, load_bundles, schedule_book

BUCKET = timedelta(minutes=10)
PERIOD_LABEL = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner"}
LEVEL_WORD = {"crowded": "is crowded", "near_capacity": "is nearly full", "busy": "is busy", "normal": "has seats"}
SENSOR_DETAIL = "seat numbers hidden from students"
STALE_DETAIL = "stream online"


def zone_names(session: Session) -> dict[str, tuple[str, str]]:
    rows = session.execute(
        select(models.SeatingZone.id, models.SeatingZone.name, models.Canteen.name).join(
            models.Canteen, models.Canteen.id == models.SeatingZone.canteen_id
        )
    )
    return {str(zone_id): (canteen, zone) for zone_id, zone, canteen in rows}


def alert_schema(
    alert: models.StaffAlert, zones: dict[str, tuple[str, str]], by_device: dict[str, list[str]]
) -> staff.StaffAlert:
    if alert.type == "sensor_offline" and alert.device_id:
        places = [zones[z] for z in by_device.get(alert.device_id, []) if z in zones]
        where = f"{places[0][0]} — {', '.join(p[1] for p in places)}" if places else "no zones"
        title, detail = f"{alert.device_id} · {where}", SENSOR_DETAIL
    else:
        canteen, zone = zones.get(str(alert.zone_id), ("Unknown canteen", "unknown zone"))
        title, detail = f"{canteen} — {zone}", STALE_DETAIL if alert.type == "data_stale" else None
    return staff.StaffAlert(
        id=str(alert.id),
        type=alert.type,  # type: ignore[arg-type]
        level=alert.level,  # type: ignore[arg-type]
        title=title,
        detail=detail,
        status=alert.status,  # type: ignore[arg-type]
        opened_at=alert.opened_at,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
    )


def device_zones(session: Session) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for zone_id, device_id in zone_devices(session).items():
        grouped[device_id].append(zone_id)
    return grouped


def alert_canteen(session: Session, alert: models.StaffAlert) -> str | None:
    if alert.zone_id is not None:
        zone = session.get(models.SeatingZone, alert.zone_id)
        return zone.canteen_id if zone else None
    device = session.get(models.Device, alert.device_id) if alert.device_id else None
    return device.canteen_id if device else None


def staff_alerts(
    session: Session, statuses: tuple[str, ...] | None = None, canteen_ids: set[str] | None = None
) -> list[staff.StaffAlert]:
    stmt = select(models.StaffAlert).order_by(models.StaffAlert.opened_at.desc())
    if statuses:
        stmt = stmt.where(models.StaffAlert.status.in_(statuses))
    zones, by_device = zone_names(session), device_zones(session)
    alerts = list(session.scalars(stmt))
    if canteen_ids is not None:
        alerts = [a for a in alerts if alert_canteen(session, a) in canteen_ids]
    return [alert_schema(a, zones, by_device) for a in alerts]


def _console_zones(bundles: list[CanteenBundle]) -> list[staff.ConsoleZone]:
    result = []
    for b in bundles:
        for z in b.zones:
            numbers = z.free_about is not None and z.free_range is not None
            result.append(
                staff.ConsoleZone(
                    zone_id=z.zone_id,
                    name=z.name,
                    canteen_name=b.canteen.name,
                    capacity=z.capacity,
                    freshness=z.freshness,
                    level=z.level,
                    occupied=z.capacity - z.free_about if numbers and z.free_about is not None else None,
                    occupied_range=(z.capacity - z.free_range[1], z.capacity - z.free_range[0])
                    if numbers and z.free_range
                    else None,
                    updated_at=z.updated_at,
                )
            )
    return result


def _devices(session: Session, now: datetime) -> list[staff.DeviceHealth]:
    zones, by_device = zone_names(session), device_zones(session)
    last_reading = dict(
        session.execute(
            select(models.OccupancyReading.device_id, models.OccupancyReading.captured_at)
            .ext(distinct_on(models.OccupancyReading.device_id))
            .order_by(models.OccupancyReading.device_id, models.OccupancyReading.captured_at.desc())
        ).all()
    )
    beats = {
        b.device_id: b
        for b in session.scalars(
            select(models.DeviceHeartbeat)
            .ext(distinct_on(models.DeviceHeartbeat.device_id))
            .order_by(models.DeviceHeartbeat.device_id, models.DeviceHeartbeat.received_at.desc())
        )
    }
    result = []
    campus_devices = select(models.Device).where(models.Device.canteen_id.in_(models.campus_canteen_ids()))
    for device in session.scalars(campus_devices.order_by(models.Device.canteen_id, models.Device.id)):
        places = [zones[z] for z in by_device.get(device.id, []) if z in zones]
        where = f"{places[0][0]} · {', '.join(p[1] for p in places)}" if places else "no zones"
        seen = device.last_heartbeat_at
        if seen is None or now - seen > OFFLINE_AFTER or not device.is_enabled:
            status = "offline"
        elif last_reading.get(device.id) is None or now - last_reading[device.id] > OFFLINE_AFTER:
            status = "not_reporting"
        else:
            status = "ok"
        beat = beats.get(device.id)
        result.append(
            staff.DeviceHealth(
                id=device.id,
                where=where,
                status=status,  # type: ignore[arg-type]
                fps=beat.fps if beat else None,
                latency_ms=beat.latency_ms if beat else None,
                last_seen_at=seen or last_reading.get(device.id),
            )
        )
    return result


def _occupancy_today(session: Session, bundle: CanteenBundle | None, now: datetime) -> staff.OccupancyToday:
    if bundle is None:
        return staff.OccupancyToday(canteen_name="No canteens yet", points=[])
    start = at_local(local_date(now), datetime.min.time())
    zone_ids = [uuid.UUID(z.zone_id) for z in bundle.zones]
    rows = session.execute(
        select(
            models.OccupancyReading.zone_id,
            models.OccupancyReading.captured_at,
            models.OccupancyReading.estimated_occupied,
            models.OccupancyReading.capacity_snapshot,
        ).where(models.OccupancyReading.zone_id.in_(zone_ids), models.OccupancyReading.captured_at >= start)
    )
    buckets: dict[int, dict[uuid.UUID, list[tuple[int, int]]]] = defaultdict(lambda: defaultdict(list))
    for zone_id, captured_at, occupied, capacity in rows:
        buckets[int((captured_at - start) / BUCKET)][zone_id].append((occupied, capacity))
    points = []
    for index in sorted(buckets):
        occupied = capacity = 0.0
        for samples in buckets[index].values():
            occupied += sum(o for o, _ in samples) / len(samples)
            capacity += samples[-1][1]
        if capacity:
            points.append(
                staff.OccupancyPoint(
                    at=start + index * BUCKET, percent=round(occupied / capacity * 100), is_forecast=False
                )
            )
    points += [
        staff.OccupancyPoint(at=p.at, percent=round(p.mean), is_forecast=True)
        for p in bundle_forecast(session, bundle, now)
    ]
    return staff.OccupancyToday(canteen_name=bundle.canteen.name, points=points)


def _console_safety(session: Session, now: datetime, simulation_mode: bool) -> staff.ConsoleSafety:
    sources = list(session.scalars(select(SafetySource).where(SafetySource.is_enabled)))
    simulator = next((s for s in sources if s.kind == "simulator"), None)
    _, events = public_status(session)
    return staff.ConsoleSafety(
        simulation_mode=simulation_mode,
        events=events,
        source=staff.SafetySource(
            name=simulator.name if simulator else "Safety simulator",
            online=simulator is not None and source_online(simulator, now),
            last_heartbeat_at=simulator.last_heartbeat_at if simulator else None,
        ),
        real_integration_connected=any(s.kind == "approved_integration" and source_online(s, now) for s in sources),
    )


def console_overview(
    session: Session,
    now: datetime,
    simulation_mode: bool,
    canteen_id: str | None,
    scope: set[str] | None = None,
) -> staff.ConsoleOverview:
    bundles = load_bundles(session, now)
    chosen = next((b for b in bundles if b.canteen.id == canteen_id), None) if canteen_id else None
    if chosen is None:
        chosen = next((b for b in bundles if b.occupancy.freshness == "live"), bundles[0] if bundles else None)
    return staff.ConsoleOverview(
        server_time=now,
        is_sample=any(b.canteen.is_sample for b in bundles),
        zones=_console_zones(bundles),
        alerts=staff_alerts(session, ("open", "acknowledged", "suspended"), scope),
        devices=_devices(session, now),
        occupancy_today=_occupancy_today(session, chosen, now),
        safety=_console_safety(session, now, simulation_mode),
    )


def _walk_minutes(session: Session) -> dict[tuple[str, str], int]:
    rows = session.execute(
        select(models.WalkingTime.from_canteen_id, models.WalkingTime.to_canteen_id, models.WalkingTime.minutes)
    )
    return {(a, b): m for a, b, m in rows}


def notices(session: Session, now: datetime) -> staff.AlertFeed:
    today = local_date(now)
    day_start = at_local(today, datetime.min.time())
    bundles = load_bundles(session, now)
    by_zone = {z.zone_id: (b, z) for b in bundles for z in b.zones}
    walks = _walk_minutes(session)
    items: list[staff.Notice] = []

    crowding = session.scalars(
        select(models.StaffAlert).where(models.StaffAlert.type == "crowding", models.StaffAlert.opened_at >= day_start)
    )
    for alert in crowding:
        found = by_zone.get(str(alert.zone_id))
        if found is None:
            continue
        bundle, zone = found
        others = [(b.canteen.id, b.occupancy) for b in bundles if b.canteen.id != bundle.canteen.id]
        best_id = best_candidate(others)
        best = next((b for b in bundles if b.canteen.id == best_id), None)
        body = (
            f"About {zone.percent}% of seats in use (estimate)."
            if zone.percent is not None
            else "Seat estimate unavailable right now."
        )
        if best and best.occupancy.free_about is not None:
            minutes = walks.get((bundle.canteen.id, best.canteen.id))
            walk = f", {minutes} min walk" if minutes else ""
            body += f" {best.canteen.name} has around {best.occupancy.free_about} free seats{walk}."
        items.append(
            staff.Notice(
                id=f"crowding-{alert.id}",
                kind="crowding",
                title=f"{bundle.canteen.name} {zone.name} {LEVEL_WORD.get(alert.level or 'crowded', 'is crowded')}",
                body=body,
                context=f"try {best.canteen.name}" if best else bundle.canteen.name,
                at=alert.opened_at,
                related_canteen=staff.RelatedCanteen(id=best.canteen.id, name=best.canteen.name) if best else None,
            )
        )

    for bundle in bundles:
        for zone in bundle.zones:
            if zone.freshness == "unavailable" and zone.updated_at is not None and zone.updated_at >= day_start:
                items.append(
                    staff.Notice(
                        id=f"unavailable-{zone.zone_id}",
                        kind="data_unavailable",
                        title=f"{bundle.canteen.name} {zone.name.lower()} — no live data",
                        body="Seat numbers for this zone are hidden until the sensor reconnects.",
                        context=bundle.canteen.name,
                        at=zone.updated_at,
                        related_canteen=None,
                    )
                )
        for shop in bundle.shops:
            if shop.status.state == "closes_soon" and shop.status.closes_at_local:
                closes = datetime.strptime(shop.status.closes_at_local, "%H:%M").time()
                reason = f" · {shop.status.reason}" if shop.status.reason else ""
                items.append(
                    staff.Notice(
                        id=f"closing-{shop.id}",
                        kind="shop_closing",
                        title=f"{shop.name} closes at {twelve_hour(closes)}",
                        body=f"{bundle.canteen.name}{reason}",
                        context=bundle.canteen.name,
                        at=at_local(today, closes) - timedelta(minutes=30),
                        related_canteen=None,
                    )
                )

    sold_out = session.execute(
        select(models.MenuItem, models.Shop.name, models.Canteen.name)
        .join(models.Shop, models.Shop.id == models.MenuItem.shop_id)
        .join(models.Canteen, models.Canteen.id == models.Shop.canteen_id)
        .where(
            ~models.MenuItem.is_available,
            models.MenuItem.is_published,
            models.MenuItem.availability_updated_at >= day_start,
        )
    )
    for item, shop_name, canteen_name in sold_out:
        items.append(
            staff.Notice(
                id=f"soldout-{item.id}",
                kind="sold_out",
                title=f"{item.name} sold out",
                body=f"{shop_name} · {canteen_name}",
                context=shop_name,
                at=item.availability_updated_at,
                related_canteen=None,
            )
        )

    for window in meal_status(now, schedule_book(session, None)).today:
        if window.starts <= now:
            label = twelve_hour(local(window.ends).time())
            items.append(
                staff.Notice(
                    id=f"meal-{today.isoformat()}-{window.period}",
                    kind="meal_starting",
                    title=f"{PERIOD_LABEL[window.period]} has started",
                    body=f"Served until {label} today.",
                    context=f"Served until {label}",
                    at=window.starts,
                    related_canteen=None,
                )
            )

    items.sort(key=lambda n: n.at, reverse=True)
    active, events = public_status(session)
    return staff.AlertFeed(server_time=now, safety=schemas.SafetyStatus(active=active, events=events), notices=items)
