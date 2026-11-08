import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.services.forecast import Prediction, slot_start
from app.services.history import canteen_forecast, canteen_series
from app.services.meal_status import Override, ScheduleBook, WeeklySlot, Window, meal_status, weekday_short
from app.services.occupancy import CanteenOccupancy, Reading, ZoneView, best_candidate, canteen_occupancy, zone_view
from app.services.shop_status import HoursException, hours_label, shop_status
from app.services.timeutil import at_local, hm, local, local_date

FEATURED_SHOPS_PER_CANTEEN = 2
FEATURED_SHOPS_LIMIT = 4
BUSY_WINDOW = timedelta(minutes=30)
BUSY_MEASURED_POINTS = 5
BUSY_FORECAST_HORIZONS = (30, 60)


@dataclass
class CanteenBundle:
    canteen: models.Canteen
    zones: list[ZoneView]
    occupancy: CanteenOccupancy
    shops: list[schemas.Shop]


def load_shops(session: Session, canteen_id: str | None = None) -> list[models.Shop]:
    stmt = (
        select(models.Shop)
        .options(selectinload(models.Shop.hours), selectinload(models.Shop.exceptions))
        .order_by(models.Shop.canteen_id, models.Shop.sort_order, models.Shop.name)
    )
    if canteen_id is not None:
        stmt = stmt.where(models.Shop.canteen_id == canteen_id)
    return list(session.scalars(stmt))


def shop_view(shop: models.Shop, canteen_name: str, now: datetime) -> schemas.Shop:
    weekly: dict[int, list[tuple[time, time]]] = defaultdict(list)
    for h in shop.hours:
        weekly[h.weekday].append((h.opens, h.closes))
    exceptions = [HoursException(e.date, e.is_closed, e.opens, e.closes, e.reason) for e in shop.exceptions]
    status = shop_status(now, weekly, exceptions, shop.temporarily_closed_until, shop.closure_reason)
    return schemas.Shop(
        id=shop.id,
        name=shop.name,
        canteen_id=shop.canteen_id,
        canteen_name=canteen_name,
        kind=shop.kind,  # type: ignore[arg-type]
        is_sample=shop.is_sample,
        status=schemas.ShopStatus(
            state=status.state,
            closes_at_local=status.closes_at_local,
            opens_at_local=status.opens_at_local,
            reason=status.reason,
        ),
        hours_label=hours_label(weekly),
        menu_updated_at=shop.menu_updated_at,
    )


def is_open(shop: schemas.Shop) -> bool:
    return shop.status.state in ("open", "closes_soon")


def latest_readings(session: Session, zone_ids: list[object]) -> dict[object, Reading]:
    if not zone_ids:
        return {}
    r = models.OccupancyReading
    stmt = (
        select(r).where(r.zone_id.in_(zone_ids)).ext(distinct_on(r.zone_id)).order_by(r.zone_id, r.captured_at.desc())
    )
    return {
        row.zone_id: Reading(
            row.captured_at, row.estimated_occupied, row.occupied_low, row.occupied_high, row.capacity_snapshot
        )
        for row in session.scalars(stmt)
    }


def nearest_walks(session: Session) -> dict[str, schemas.WalkTime]:
    rows = session.execute(
        select(models.WalkingTime.to_canteen_id, models.WalkingTime.minutes, models.Canteen.name)
        .join(models.Canteen, models.Canteen.id == models.WalkingTime.from_canteen_id)
        .order_by(models.WalkingTime.minutes)
    )
    walks: dict[str, schemas.WalkTime] = {}
    for to_id, minutes, from_name in rows:
        walks.setdefault(to_id, schemas.WalkTime(from_name=from_name, minutes=minutes))
    return walks


def load_bundles(session: Session, now: datetime, canteen_id: str | None = None) -> list[CanteenBundle]:
    stmt = (
        select(models.Canteen)
        .options(selectinload(models.Canteen.zones), selectinload(models.Canteen.hours))
        .where(models.Canteen.kind == models.CANTEEN)
        .order_by(models.Canteen.sort_order, models.Canteen.name)
    )
    if canteen_id is not None:
        stmt = stmt.where(models.Canteen.id == canteen_id)
    canteens = list(session.scalars(stmt))
    active_zones = [z for c in canteens for z in c.zones if z.is_active]
    readings = latest_readings(session, [z.id for z in active_zones])
    shops_by_canteen: dict[str, list[models.Shop]] = defaultdict(list)
    for shop in load_shops(session, canteen_id):
        shops_by_canteen[shop.canteen_id].append(shop)
    bundles = []
    for c in canteens:
        zones = [
            zone_view(str(z.id), z.name, z.capacity, readings.get(z.id) if z.is_monitored else None, now)
            for z in c.zones
            if z.is_active
        ]
        shops = [shop_view(s, c.name, now) for s in shops_by_canteen[c.id]]
        bundles.append(CanteenBundle(canteen=c, zones=zones, occupancy=canteen_occupancy(zones), shops=shops))
    return bundles


def canteen_summary(bundle: CanteenBundle, walks: dict[str, schemas.WalkTime]) -> schemas.CanteenSummary:
    o = bundle.occupancy
    return schemas.CanteenSummary(
        id=bundle.canteen.id,
        name=bundle.canteen.name,
        is_sample=bundle.canteen.is_sample,
        level=o.level,
        freshness=o.freshness,
        percent=o.percent,
        free_about=o.free_about,
        free_range=o.free_range,
        monitored_capacity=o.monitored_capacity,
        zones_live=o.zones_live,
        zones_total=o.zones_total,
        shops_total=len(bundle.shops),
        shops_open=sum(1 for s in bundle.shops if is_open(s)),
        walk=walks.get(bundle.canteen.id),
        updated_at=o.updated_at,
    )


def zone_schema(z: ZoneView) -> schemas.ZoneOccupancy:
    return schemas.ZoneOccupancy(
        zone_id=z.zone_id,
        name=z.name,
        capacity=z.capacity,
        freshness=z.freshness,
        level=z.level,
        percent=z.percent,
        free_about=z.free_about,
        free_range=z.free_range,
        updated_at=z.updated_at,
    )


def hours_today(canteen: models.Canteen, now: datetime) -> list[schemas.OpeningHours]:
    weekday = local_date(now).weekday()
    return [schemas.OpeningHours(opens=hm(h.opens), closes=hm(h.closes)) for h in canteen.hours if h.weekday == weekday]


def featured_shops(bundles: list[CanteenBundle]) -> list[schemas.Shop]:
    picked = [s for b in bundles for s in b.shops[:FEATURED_SHOPS_PER_CANTEEN]]
    return picked[:FEATURED_SHOPS_LIMIT]


def pick_best(bundles: list[CanteenBundle]) -> schemas.BestCanteen | None:
    best_id = best_candidate([(b.canteen.id, b.occupancy) for b in bundles])
    if best_id is None:
        return None
    best = next(b for b in bundles if b.canteen.id == best_id)
    return schemas.BestCanteen(canteen_id=best.canteen.id, name=best.canteen.name)


def schedule_book(session: Session, canteen_id: str | None) -> ScheduleBook:
    owners = [None] if canteen_id is None else [None, canteen_id]
    ms, so = models.MealSchedule, models.ScheduleOverride
    weekly = [
        WeeklySlot(r.canteen_id, r.weekday, r.period, r.starts, r.ends)
        for r in session.scalars(
            select(ms).where(ms.canteen_id.is_(None) | ms.canteen_id.in_([o for o in owners if o]))
        )
    ]
    overrides = [
        Override(r.canteen_id, r.date, r.period, r.is_cancelled, r.starts, r.ends, r.reason)
        for r in session.scalars(
            select(so).where(so.canteen_id.is_(None) | so.canteen_id.in_([o for o in owners if o]))
        )
    ]
    return ScheduleBook(weekly=weekly, overrides=overrides, canteen_id=canteen_id)


def _window(w: Window) -> schemas.MealWindow:
    return schemas.MealWindow(period=w.period, starts=w.starts, ends=w.ends)  # type: ignore[arg-type]


def meal_status_schema(session: Session, now: datetime, canteen_id: str | None) -> schemas.MealStatus:
    state = meal_status(now, schedule_book(session, canteen_id))
    is_sample = session.scalar(select(models.Canteen.is_sample).where(models.Canteen.kind == models.CANTEEN).limit(1))
    return schemas.MealStatus(
        server_time=now,
        timezone="Asia/Colombo",
        is_sample=bool(is_sample),
        state=state.state,
        current=_window(state.current) if state.current else None,
        next=_window(state.next) if state.next else None,
        today=[_window(w) for w in state.today],
        week=[
            schemas.WeekDay(
                date=d.day.isoformat(),
                weekday=weekday_short(d.day),
                day=d.day.day,
                kind=d.kind,
                note=d.note,
                is_today=d.is_today,
            )
            for d in state.week
        ],
    )


def zone_uuids(bundle: CanteenBundle) -> list[uuid.UUID]:
    return [uuid.UUID(z.zone_id) for z in bundle.zones]


def bundle_forecast(session: Session, bundle: CanteenBundle, now: datetime) -> list[Prediction]:
    o = bundle.occupancy
    if o.freshness != "live" or o.percent is None:
        return []
    return canteen_forecast(session, bundle.canteen.id, zone_uuids(bundle), now, float(o.percent))


def forecast_schema(predictions: list[Prediction]) -> list[schemas.ForecastPoint]:
    return [schemas.ForecastPoint(at=p.at, low=p.low, high=p.high) for p in predictions]


def busy_today(session: Session, bundles: list[CanteenBundle], now: datetime) -> schemas.BusyToday | None:
    bundle = next((b for b in bundles if b.occupancy.freshness == "live" and b.occupancy.percent is not None), None)
    if bundle is None or bundle.occupancy.percent is None:
        return None
    start = at_local(local_date(now), time.min)
    series = canteen_series(session, zone_uuids(bundle), start, slot_start(now))
    windows: dict[datetime, list[float]] = defaultdict(list)
    for t, value in series.points.items():
        windows[start + ((t - start) // BUSY_WINDOW) * BUSY_WINDOW].append(value)
    current_window = start + ((now - start) // BUSY_WINDOW) * BUSY_WINDOW
    measured = [
        schemas.BusyPoint(label=hm(local(t).time()), percent=round(sum(v) / len(v)), is_forecast=False, is_now=False)
        for t, v in sorted(windows.items())
        if t < current_window
    ][-(BUSY_MEASURED_POINTS - 1) :]
    now_point = schemas.BusyPoint(label="Now", percent=bundle.occupancy.percent, is_forecast=False, is_now=True)
    ahead = [
        schemas.BusyPoint(
            label=hm(local(slot_start(p.at)).time()), percent=round(p.mean), is_forecast=True, is_now=False
        )
        for p in bundle_forecast(session, bundle, now)
        if p.horizon in BUSY_FORECAST_HORIZONS
    ]
    return schemas.BusyToday(
        canteen_id=bundle.canteen.id, canteen_name=bundle.canteen.name, points=[*measured, now_point, *ahead]
    )
