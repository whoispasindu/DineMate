import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select, update

from app import models
from app.business.service import update_tables
from app.core.auth import StaffUser, can_manage_canteen, forbidden_scope
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import DeviceDep, RealNowDep
from app.core.errors import ApiError, not_found
from app.routers.devices import AUTH_RESPONSES, MAX_FUTURE_SKEW, camera_zones, current_layout
from app.schemas import ErrorResponse
from app.schemas_seats import (
    CanteenSeats,
    CanteenSeatTotals,
    SeatDetail,
    SeatOverview,
    SeatsAccepted,
    SeatSnapshotIn,
    StayHour,
    StayTimes,
    ZoneSeatMap,
    ZoneSeats,
)
from app.services.occupancy import freshness_for
from app.services.stays import likely_to_free, median_by_hour, stay_minutes

router = APIRouter(tags=["seats"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}


def seating_polygons(layout: models.ZoneLayout | None) -> dict[str, dict[str, Any]]:
    if layout is None:
        return {}
    return {str(p["zone_id"]): p for p in layout.polygons if p.get("type") == "seating" and p.get("zone_id")}


@router.post("/devices/{device_id}/seats", response_model=SeatsAccepted, responses=AUTH_RESPONSES)
def post_seats(
    payload: SeatSnapshotIn, device: DeviceDep, session: SessionDep, now: NowDep, real_now: RealNowDep
) -> SeatsAccepted:
    if payload.captured_at > real_now + MAX_FUTURE_SKEW:
        raise ApiError(
            422,
            "validation_error",
            "captured_at is more than 60 s in the future.",
            {"captured_at": payload.captured_at.isoformat()},
        )
    polygons = seating_polygons(current_layout(session, device.id))
    mentioned = {z.zone_id for z in payload.zones} | {s.zone_id for s in payload.seats}
    unknown = sorted(mentioned - set(polygons))
    if unknown:
        raise ApiError(
            422, "validation_error", "Seats include zones this device does not cover.", {"zone_ids": unknown}
        )
    known = {(zone_id, str(seat["seat_id"])) for zone_id, p in polygons.items() for seat in p.get("seats", [])}
    stray = sorted({s.seat_id for s in payload.seats if (s.zone_id, s.seat_id) not in known})
    if stray:
        raise ApiError(422, "validation_error", "Seats are not in this device's layout.", {"seat_ids": stray})
    captured_at = now - max(timedelta(0), real_now - payload.captured_at)
    simulated = device.kind == "simulator"
    if simulated:
        taken = camera_zones(session, now)
        payload.zones = [z for z in payload.zones if z.zone_id not in taken]
        payload.seats = [s for s in payload.seats if s.zone_id not in taken]
    for zone in payload.zones:
        session.merge(
            models.ZoneSeatStatus(
                zone_id=uuid.UUID(zone.zone_id),
                device_id=device.id,
                captured_at=captured_at,
                free=zone.free,
                occupied=zone.occupied,
                held=zone.held,
                unknown=zone.unknown,
                free_soon=zone.free_soon,
                standing=zone.standing,
                crowded=zone.crowded,
                is_simulated=simulated,
            )
        )
    zone_uuids = {uuid.UUID(s.zone_id) for s in payload.seats}
    states = {
        (str(s.zone_id), s.seat_id): s
        for s in session.scalars(select(models.SeatState).where(models.SeatState.zone_id.in_(zone_uuids)))
    }
    changed = 0
    for seat in payload.seats:
        started = captured_at - timedelta(seconds=seat.for_s)
        zone_uuid = uuid.UUID(seat.zone_id)
        current = states.get((seat.zone_id, seat.seat_id))
        if current is None or current.state != seat.state:
            ss = models.SeatSession
            session.execute(
                update(ss)
                .where(ss.zone_id == zone_uuid, ss.seat_id == seat.seat_id, ss.ended_at.is_(None))
                .values(ended_at=func.greatest(started, ss.started_at))
            )
            session.add(
                ss(
                    zone_id=zone_uuid,
                    seat_id=seat.seat_id,
                    state=seat.state,
                    started_at=started,
                    is_simulated=simulated,
                )
            )
            changed += 1
            if current is None:
                current = models.SeatState(
                    zone_id=zone_uuid, seat_id=seat.seat_id, state=seat.state, since=started, updated_at=captured_at
                )
                session.add(current)
            else:
                current.state, current.since = seat.state, started
        current.free_soon = seat.free_soon
        current.updated_at = captured_at
    if models.is_venue_id(device.canteen_id):
        touched = zone_uuids | {uuid.UUID(z.zone_id) for z in payload.zones}
        update_tables(session, touched, captured_at, simulated)
    device.last_heartbeat_at = now
    session.commit()
    return SeatsAccepted(
        server_time=now, device_id=device.id, zones=len(payload.zones), seats=len(payload.seats), changed=changed
    )


def zone_seats(zone: models.SeatingZone, status: models.ZoneSeatStatus, now: datetime) -> ZoneSeats:
    freshness = freshness_for(status.captured_at, now)
    hidden = freshness == "unavailable"
    return ZoneSeats(
        zone_id=str(zone.id),
        name=zone.name,
        freshness=freshness,
        seats=status.free + status.occupied + status.held + status.unknown,
        free=None if hidden else status.free,
        occupied=None if hidden else status.occupied,
        held=None if hidden else status.held,
        unknown=None if hidden else status.unknown,
        free_soon=None if hidden else status.free_soon,
        standing=None if hidden else status.standing,
        crowded=False if hidden else status.crowded,
        updated_at=status.captured_at,
    )


def zone_statuses(session: SessionDep, canteen_id: str | None = None) -> list[tuple[models.SeatingZone, Any]]:
    query = (
        select(models.SeatingZone, models.ZoneSeatStatus)
        .join(models.ZoneSeatStatus, models.ZoneSeatStatus.zone_id == models.SeatingZone.id)
        .where(models.SeatingZone.is_active, models.SeatingZone.canteen_id.in_(models.campus_canteen_ids()))
        .order_by(models.SeatingZone.canteen_id, models.SeatingZone.sort_order, models.SeatingZone.name)
    )
    if canteen_id is not None:
        query = query.where(models.SeatingZone.canteen_id == canteen_id)
    return [(zone, status) for zone, status in session.execute(query)]


@router.get("/canteens/{canteen_id}/seats", response_model=CanteenSeats, responses=NOT_FOUND)
def get_canteen_seats(canteen_id: str, session: SessionDep, now: NowDep) -> CanteenSeats:
    if models.is_venue_id(canteen_id) or session.get(models.Canteen, canteen_id) is None:
        raise not_found("Canteen", canteen_id)
    zones = [zone_seats(zone, status, now) for zone, status in zone_statuses(session, canteen_id)]
    return CanteenSeats(
        server_time=now,
        canteen_id=canteen_id,
        zones=zones,
        held=sum(z.held or 0 for z in zones),
        free_soon=sum(z.free_soon or 0 for z in zones),
        crowded_zones=sum(1 for z in zones if z.crowded),
    )


@router.get("/seats/overview", response_model=SeatOverview)
def get_seat_overview(session: SessionDep, now: NowDep) -> SeatOverview:
    grouped: dict[str, list[ZoneSeats]] = defaultdict(list)
    for zone, status in zone_statuses(session):
        grouped[zone.canteen_id].append(zone_seats(zone, status, now))
    return SeatOverview(
        server_time=now,
        items=[
            CanteenSeatTotals(
                canteen_id=canteen_id,
                zones_with_seats=len(zones),
                held=sum(z.held or 0 for z in zones),
                free_soon=sum(z.free_soon or 0 for z in zones),
                crowded_zones=sum(1 for z in zones if z.crowded),
            )
            for canteen_id, zones in grouped.items()
        ],
    )


@router.get("/zones/{zone_id}/seats", response_model=ZoneSeatMap, responses=NOT_FOUND)
def get_zone_seat_map(zone_id: str, user: StaffUser, session: SessionDep, now: NowDep) -> ZoneSeatMap:
    try:
        zone_uuid = uuid.UUID(zone_id)
    except ValueError as exc:
        raise not_found("Zone", zone_id) from exc
    zone = session.get(models.SeatingZone, zone_uuid)
    if zone is None:
        raise not_found("Zone", zone_id)
    if not can_manage_canteen(user, zone.canteen_id):
        raise forbidden_scope("You can only see seats in your own canteens.", zone_id=zone_id)
    positions: list[dict[str, Any]] = []
    for device in session.scalars(select(models.Device).where(models.Device.canteen_id == zone.canteen_id)):
        polygon = seating_polygons(current_layout(session, device.id)).get(zone_id)
        if polygon and polygon.get("seats"):
            positions = list(polygon["seats"])
            break
    states = {
        s.seat_id: s for s in session.scalars(select(models.SeatState).where(models.SeatState.zone_id == zone_uuid))
    }
    status = session.get(models.ZoneSeatStatus, zone_uuid)
    freshness = freshness_for(status.captured_at if status else None, now)
    seats = []
    for seat in positions:
        state = states.get(str(seat["seat_id"]))
        shown = state if state is not None and freshness != "unavailable" else None
        seats.append(
            SeatDetail.model_validate(
                {
                    "seat_id": str(seat["seat_id"]),
                    "x": float(seat["x"]),
                    "y": float(seat["y"]),
                    "state": shown.state if shown else "unknown",
                    "since": shown.since if shown else None,
                    "free_soon": bool(shown and shown.free_soon),
                }
            )
        )
    return ZoneSeatMap(server_time=now, zone_id=zone_id, name=zone.name, freshness=freshness, seats=seats)


@router.get("/canteens/{canteen_id}/stay-times", response_model=StayTimes, responses=NOT_FOUND)
def get_stay_times(
    canteen_id: str,
    user: StaffUser,
    session: SessionDep,
    now: NowDep,
    days: Annotated[int, Query(ge=1, le=28)] = 7,
) -> StayTimes:
    if session.get(models.Canteen, canteen_id) is None:
        raise not_found("Canteen", canteen_id)
    if not can_manage_canteen(user, canteen_id):
        raise forbidden_scope("You can only see stay times for your own canteens.", canteen_id=canteen_id)
    ss = models.SeatSession
    zone_ids = select(models.SeatingZone.id).where(models.SeatingZone.canteen_id == canteen_id)
    closed = session.execute(
        select(ss.started_at, ss.ended_at).where(
            ss.zone_id.in_(zone_ids),
            ss.state == "occupied",
            ss.ended_at.is_not(None),
            ss.started_at >= now - timedelta(days=days),
        )
    ).all()
    pairs = [(started, ended) for started, ended in closed if ended is not None]
    durations = [m for started, ended in pairs if (m := stay_minutes(started, ended)) is not None]
    open_now = session.scalars(
        select(ss.started_at).where(ss.zone_id.in_(zone_ids), ss.state == "occupied", ss.ended_at.is_(None))
    ).all()
    elapsed = [max(0.0, (now - started).total_seconds() / 60) for started in open_now]
    return StayTimes(
        server_time=now,
        canteen_id=canteen_id,
        days=days,
        sessions=len(durations),
        median_minutes=round(median(durations), 1) if durations else None,
        hours=[
            StayHour(hour=hour, median_minutes=value, sessions=count)
            for hour, (value, count) in median_by_hour(pairs).items()
        ],
        occupied_now=len(elapsed),
        likely_free_10min=likely_to_free(elapsed, durations),
        is_experimental=True,
    )
