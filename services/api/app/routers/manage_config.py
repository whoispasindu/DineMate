import uuid
from collections import defaultdict
from itertools import pairwise
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import delete, select

from app import models
from app.core.auth import ADMIN, StaffUser, can_manage_canteen, forbidden_scope
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import RealNowDep
from app.core.errors import ApiError, not_found
from app.schemas import ErrorResponse
from app.schemas_config import (
    MealOverride,
    MealScheduleIn,
    MealScheduleSet,
    MealSlot,
    ThresholdList,
    ThresholdResult,
    ThresholdValues,
    ZoneThresholds,
)
from app.services.audit import record
from app.services.crowding import CrowdThresholds

router = APIRouter(tags=["configuration"])

CAMPUS = "Campus default"
RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}
DEFAULTS = CrowdThresholds()


def invalid(message: str, **details: Any) -> ApiError:
    return ApiError(422, "validation_error", message, details or None)


def owner_name(session: SessionDep, canteen_id: str | None) -> str:
    if canteen_id is None:
        return CAMPUS
    canteen = session.get(models.Canteen, canteen_id)
    if canteen is None:
        raise not_found("Canteen", canteen_id)
    return canteen.name


def _slots(session: SessionDep, canteen_id: str | None) -> list[MealSlot]:
    ms = models.MealSchedule
    owner = ms.canteen_id.is_(None) if canteen_id is None else ms.canteen_id == canteen_id
    rows = session.scalars(select(ms).where(owner).order_by(ms.weekday, ms.starts))
    return [MealSlot(weekday=r.weekday, period=r.period, starts=r.starts, ends=r.ends) for r in rows]  # type: ignore[arg-type]


def _overrides(session: SessionDep, canteen_id: str | None) -> list[MealOverride]:
    so = models.ScheduleOverride
    owner = so.canteen_id.is_(None) if canteen_id is None else so.canteen_id == canteen_id
    rows = session.scalars(select(so).where(owner).order_by(so.date, so.starts))
    return [
        MealOverride(
            date=r.date,
            period=r.period,  # type: ignore[arg-type]
            is_cancelled=r.is_cancelled,
            starts=r.starts,
            ends=r.ends,
            reason=r.reason,
        )
        for r in rows
    ]


def schedule_set(session: SessionDep, user: models.User, canteen_id: str | None, now: Any) -> MealScheduleSet:
    name = owner_name(session, canteen_id)
    weekly = _slots(session, canteen_id)
    campus = weekly if canteen_id is None else _slots(session, None)
    return MealScheduleSet(
        server_time=now,
        canteen_id=canteen_id,
        canteen_name=name,
        uses_campus_weekly=canteen_id is not None and not weekly,
        weekly=weekly or campus,
        campus_weekly=campus,
        overrides=_overrides(session, canteen_id),
        can_edit=user.role == ADMIN if canteen_id is None else can_manage_canteen(user, canteen_id),
    )


def validate_schedule(payload: MealScheduleIn) -> None:
    if payload.weekly is None and payload.canteen_id is None:
        raise invalid("The campus schedule needs weekly meal times.")
    by_day: dict[int, list[MealSlot]] = defaultdict(list)
    for slot in payload.weekly or []:
        if slot.starts >= slot.ends:
            raise invalid("Meal start must be before its end.", weekday=slot.weekday, period=slot.period)
        if any(s.period == slot.period for s in by_day[slot.weekday]):
            raise invalid("Each meal can appear once per day.", weekday=slot.weekday, period=slot.period)
        by_day[slot.weekday].append(slot)
    for weekday, slots in by_day.items():
        for earlier, later in pairwise(sorted(slots, key=lambda s: s.starts)):
            if later.starts < earlier.ends:
                raise invalid("Meals on the same day can't overlap.", weekday=weekday)
    seen: set[tuple[str, str | None]] = set()
    for o in payload.overrides:
        key = (o.date.isoformat(), o.period)
        if key in seen:
            raise invalid("Each meal can have one override per date.", date=key[0])
        seen.add(key)
        if o.is_cancelled:
            continue
        if o.period is None or o.starts is None or o.ends is None or o.starts >= o.ends:
            raise invalid("Changed meal times need a meal and a start before the end.", date=key[0])


@router.get("/manage/meal-schedules", response_model=MealScheduleSet, responses=RESPONSES)
def get_meal_schedules(
    user: StaffUser, session: SessionDep, now: NowDep, canteen_id: str | None = None
) -> MealScheduleSet:
    if canteen_id is not None and not can_manage_canteen(user, canteen_id):
        owner_name(session, canteen_id)
        raise forbidden_scope("You can only view schedules for your own canteens.", canteen_id=canteen_id)
    return schedule_set(session, user, canteen_id, now)


@router.put("/meal-schedules", response_model=MealScheduleSet, responses=RESPONSES)
def put_meal_schedules(
    payload: MealScheduleIn,
    user: StaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> MealScheduleSet:
    owner = payload.canteen_id
    owner_name(session, owner)
    if owner is None and user.role != ADMIN:
        raise forbidden_scope("Only campus admins can change the campus schedule.")
    if owner is not None and not can_manage_canteen(user, owner):
        raise forbidden_scope("You can only change schedules for your own canteens.", canteen_id=owner)
    validate_schedule(payload)
    ms, so = models.MealSchedule, models.ScheduleOverride
    before = {
        "weekly": [s.model_dump() for s in _slots(session, owner)],
        "overrides": [o.model_dump() for o in _overrides(session, owner)],
    }
    session.execute(delete(ms).where(ms.canteen_id.is_(None) if owner is None else ms.canteen_id == owner))
    session.execute(delete(so).where(so.canteen_id.is_(None) if owner is None else so.canteen_id == owner))
    for slot in payload.weekly or []:
        session.add(ms(canteen_id=owner, weekday=slot.weekday, period=slot.period, starts=slot.starts, ends=slot.ends))
    for o in payload.overrides:
        session.add(
            so(
                canteen_id=owner,
                date=o.date,
                period=o.period,
                is_cancelled=o.is_cancelled,
                starts=None if o.is_cancelled else o.starts,
                ends=None if o.is_cancelled else o.ends,
                reason=o.reason or None,
            )
        )
    record(
        session,
        real_now,
        "meal_schedule.update",
        "meal_schedule",
        owner or "campus",
        user=user,
        before=before,
        after=payload.model_dump(),
        request=request,
    )
    session.commit()
    return schedule_set(session, user, owner, now)


def _values(row: models.CrowdingThreshold | None) -> ThresholdValues:
    if row is None:
        return ThresholdValues(
            busy_pct=DEFAULTS.busy,
            crowded_pct=DEFAULTS.crowded,
            near_capacity_pct=DEFAULTS.near_capacity,
            hysteresis_pct=DEFAULTS.hysteresis,
            dwell_seconds=int(DEFAULTS.dwell.total_seconds()),
            alert_from=DEFAULTS.alert_from,  # type: ignore[arg-type]
        )
    return ThresholdValues(
        busy_pct=float(row.busy_pct),
        crowded_pct=float(row.crowded_pct),
        near_capacity_pct=float(row.near_capacity_pct),
        hysteresis_pct=float(row.hysteresis_pct),
        dwell_seconds=row.dwell_seconds,
        alert_from=row.alert_from,  # type: ignore[arg-type]
    )


def _zone_thresholds(zone: models.SeatingZone, row: models.CrowdingThreshold | None) -> ZoneThresholds:
    return ZoneThresholds(
        zone_id=str(zone.id),
        zone_name=zone.name,
        canteen_id=zone.canteen_id,
        canteen_name=zone.canteen.name,
        capacity=zone.capacity,
        is_monitored=zone.is_monitored,
        is_default=row is None,
        values=_values(row),
    )


@router.get("/manage/thresholds", response_model=ThresholdList, responses=RESPONSES)
def list_thresholds(user: StaffUser, session: SessionDep, now: NowDep) -> ThresholdList:
    zones = session.scalars(
        select(models.SeatingZone)
        .where(models.SeatingZone.is_active, models.SeatingZone.canteen_id.in_(models.campus_canteen_ids()))
        .order_by(models.SeatingZone.canteen_id, models.SeatingZone.sort_order)
    )
    rows = {t.zone_id: t for t in session.scalars(select(models.CrowdingThreshold))}
    items = [_zone_thresholds(z, rows.get(z.id)) for z in zones if can_manage_canteen(user, z.canteen_id)]
    return ThresholdList(server_time=now, defaults=_values(None), items=items)


@router.put("/zones/{zone_id}/thresholds", response_model=ThresholdResult, responses=RESPONSES)
def put_thresholds(
    zone_id: str,
    payload: ThresholdValues,
    user: StaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ThresholdResult:
    zone = managed_zone(session, user, zone_id)
    if not payload.busy_pct < payload.crowded_pct < payload.near_capacity_pct:
        raise invalid("Levels must rise: busy < crowded < near capacity.")
    if payload.hysteresis_pct >= payload.busy_pct:
        raise invalid("Hysteresis must be smaller than the busy level.")
    row = session.get(models.CrowdingThreshold, zone.id)
    before = _values(row).model_dump()
    if row is None:
        row = models.CrowdingThreshold(zone_id=zone.id)
        session.add(row)
    row.busy_pct, row.crowded_pct, row.near_capacity_pct = (
        payload.busy_pct,
        payload.crowded_pct,
        payload.near_capacity_pct,
    )
    row.hysteresis_pct, row.dwell_seconds, row.alert_from = (
        payload.hysteresis_pct,
        payload.dwell_seconds,
        payload.alert_from,
    )
    record(
        session,
        real_now,
        "zone.thresholds",
        "seating_zone",
        zone_id,
        user=user,
        before=before,
        after=payload.model_dump(),
        request=request,
    )
    session.commit()
    return ThresholdResult(server_time=now, item=_zone_thresholds(zone, row))


def managed_zone(session: SessionDep, user: models.User, zone_id: str) -> models.SeatingZone:
    try:
        key = uuid.UUID(zone_id)
    except ValueError as exc:
        raise not_found("Zone", zone_id) from exc
    zone = session.get(models.SeatingZone, key)
    if zone is None:
        raise not_found("Zone", zone_id)
    if not can_manage_canteen(user, zone.canteen_id):
        raise forbidden_scope("You can only change zones in your own canteens.", zone_id=zone_id)
    return zone
