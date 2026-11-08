import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select, update

from app import models
from app.core.auth import StaffUser, can_manage_canteen, forbidden_scope
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import RealNowDep
from app.core.errors import ApiError, not_found
from app.routers.devices import current_layout
from app.routers.manage_config import RESPONSES, invalid, managed_zone, owner_name
from app.schemas_config import (
    DeviceLayout,
    EditableZone,
    LayoutIn,
    LayoutPolygon,
    LayoutVersion,
    ManagedDevice,
    ManagedDeviceList,
    RollbackIn,
    ZoneIn,
    ZonePatch,
    ZoneResult,
)
from app.services.audit import record

router = APIRouter(tags=["zones"])

CONFLICT: dict[int | str, dict[str, Any]] = {**RESPONSES, 409: RESPONSES[404]}


def managed_device(session: SessionDep, user: models.User, device_id: str) -> models.Device:
    device = session.get(models.Device, device_id)
    if device is None:
        raise not_found("Device", device_id)
    if not can_manage_canteen(user, device.canteen_id):
        raise forbidden_scope("You can only edit layouts for your own canteens.", device_id=device_id)
    return device


def editable_zone(zone: models.SeatingZone) -> EditableZone:
    return EditableZone(
        id=str(zone.id),
        name=zone.name,
        capacity=zone.capacity,
        is_active=zone.is_active,
        is_monitored=zone.is_monitored,
    )


def device_layout(session: SessionDep, device: models.Device, now: Any) -> DeviceLayout:
    layout = current_layout(session, device.id)
    zl = models.ZoneLayout
    history = session.scalars(select(zl).where(zl.device_id == device.id).order_by(zl.version.desc()))
    zones = session.scalars(
        select(models.SeatingZone)
        .where(models.SeatingZone.canteen_id == device.canteen_id)
        .order_by(models.SeatingZone.sort_order, models.SeatingZone.name)
    )
    return DeviceLayout(
        server_time=now,
        device_id=device.id,
        canteen_id=device.canteen_id,
        canteen_name=owner_name(session, device.canteen_id),
        kind=device.kind,  # type: ignore[arg-type]
        version=layout.version if layout else None,
        polygons=[LayoutPolygon.model_validate(p) for p in layout.polygons] if layout else [],
        zones=[editable_zone(z) for z in zones],
        history=[
            LayoutVersion(
                version=h.version,
                created_at=h.created_at,
                is_current=h.is_current,
                seating_zones=sum(1 for p in h.polygons if p.get("type") == "seating"),
            )
            for h in history
        ],
    )


def validate_polygons(session: SessionDep, device: models.Device, polygons: list[LayoutPolygon]) -> None:
    canteen_zones = {
        str(z)
        for z in session.scalars(
            select(models.SeatingZone.id).where(models.SeatingZone.canteen_id == device.canteen_id)
        )
    }
    seen: set[str] = set()
    seat_ids: set[str] = set()
    for polygon in polygons:
        if polygon.type != "seating":
            if polygon.zone_id is not None:
                raise invalid("Only seating polygons can be linked to a zone.")
            if polygon.seats:
                raise invalid("Seats can only be placed in seating polygons.")
            continue
        if polygon.zone_id not in canteen_zones:
            raise invalid("Seating polygons must use a zone from this canteen.", zone_id=polygon.zone_id or "")
        if polygon.zone_id in seen:
            raise invalid("Each zone can be drawn once per layout.", zone_id=polygon.zone_id)
        seen.add(polygon.zone_id)
        for seat in polygon.seats:
            if seat.seat_id in seat_ids:
                raise invalid("Each seat needs its own id.", seat_id=seat.seat_id)
            seat_ids.add(seat.seat_id)
            if not inside(polygon.points, seat.x, seat.y):
                raise invalid("Seats must be inside their seating polygon.", seat_id=seat.seat_id)


def inside(polygon: Sequence[Sequence[float]], x: float, y: float) -> bool:
    result = False
    for i in range(len(polygon)):
        x1, y1 = polygon[i][0], polygon[i][1]
        x2, y2 = polygon[(i + 1) % len(polygon)][0], polygon[(i + 1) % len(polygon)][1]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            result = not result
    return result


def sync_seat_capacity(session: SessionDep, polygons: list[dict[str, Any]]) -> dict[str, int]:
    changed: dict[str, int] = {}
    for polygon in polygons:
        seats = polygon.get("seats") or []
        if polygon.get("type") != "seating" or not seats or not polygon.get("zone_id"):
            continue
        zone = session.get(models.SeatingZone, uuid.UUID(str(polygon["zone_id"])))
        if zone is not None and zone.capacity != len(seats):
            zone.capacity = len(seats)
            changed[str(zone.id)] = len(seats)
    return changed


def save_version(session: SessionDep, device: models.Device, polygons: list[dict[str, Any]]) -> int:
    zl = models.ZoneLayout
    version = (session.scalar(select(func.max(zl.version)).where(zl.device_id == device.id)) or 0) + 1
    session.execute(update(zl).where(zl.device_id == device.id).values(is_current=False))
    session.add(zl(device_id=device.id, version=version, polygons=polygons, is_current=True))
    return version


@router.get("/manage/devices", response_model=ManagedDeviceList, responses=RESPONSES)
def list_managed_devices(user: StaffUser, session: SessionDep, now: NowDep) -> ManagedDeviceList:
    names = {cid: name for cid, name in session.execute(select(models.Canteen.id, models.Canteen.name))}
    devices = session.scalars(
        select(models.Device)
        .where(models.Device.canteen_id.in_(models.campus_canteen_ids()))
        .order_by(models.Device.canteen_id, models.Device.id)
    )
    items = []
    for d in devices:
        if not can_manage_canteen(user, d.canteen_id):
            continue
        layout = current_layout(session, d.id)
        items.append(
            ManagedDevice(
                id=d.id,
                kind=d.kind,  # type: ignore[arg-type]
                canteen_id=d.canteen_id,
                canteen_name=names.get(d.canteen_id, d.canteen_id),
                layout_version=layout.version if layout else None,
                last_heartbeat_at=d.last_heartbeat_at,
                is_enabled=d.is_enabled,
            )
        )
    return ManagedDeviceList(server_time=now, items=items)


@router.get("/devices/{device_id}/layout", response_model=DeviceLayout, responses=RESPONSES)
def get_layout(device_id: str, user: StaffUser, session: SessionDep, now: NowDep) -> DeviceLayout:
    return device_layout(session, managed_device(session, user, device_id), now)


@router.put("/devices/{device_id}/layout", response_model=DeviceLayout, responses=CONFLICT)
def put_layout(
    device_id: str,
    payload: LayoutIn,
    user: StaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> DeviceLayout:
    device = managed_device(session, user, device_id)
    layout = current_layout(session, device_id)
    current = layout.version if layout else None
    if payload.base_version != current:
        raise ApiError(
            409,
            "conflict",
            "Someone saved a newer layout. Reload to see it before saving again.",
            {"current_version": current},
        )
    validate_polygons(session, device, payload.polygons)
    polygons = [p.model_dump(mode="json", exclude_none=True) for p in payload.polygons]
    version = save_version(session, device, polygons)
    capacities = sync_seat_capacity(session, polygons)
    record(
        session,
        real_now,
        "layout.save",
        "device",
        device_id,
        user=user,
        before={"version": current},
        after={
            "version": version,
            "polygons": len(polygons),
            "seats": sum(len(p.get("seats") or []) for p in polygons),
            "capacity_from_seats": capacities,
        },
        request=request,
    )
    session.commit()
    return device_layout(session, device, now)


@router.post("/devices/{device_id}/layout/rollback", response_model=DeviceLayout, responses=RESPONSES)
def rollback_layout(
    device_id: str,
    payload: RollbackIn,
    user: StaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> DeviceLayout:
    device = managed_device(session, user, device_id)
    zl = models.ZoneLayout
    source = session.scalars(select(zl).where(zl.device_id == device_id, zl.version == payload.version)).first()
    if source is None:
        raise not_found("Layout version", str(payload.version))
    current = current_layout(session, device_id)
    version = save_version(session, device, list(source.polygons))
    capacities = sync_seat_capacity(session, list(source.polygons))
    record(
        session,
        real_now,
        "layout.rollback",
        "device",
        device_id,
        user=user,
        before={"version": current.version if current else None},
        after={"version": version, "copied_from": payload.version, "capacity_from_seats": capacities},
        request=request,
    )
    session.commit()
    return device_layout(session, device, now)


@router.patch("/zones/{zone_id}", response_model=ZoneResult, responses=RESPONSES)
def patch_zone(
    zone_id: str,
    payload: ZonePatch,
    user: StaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ZoneResult:
    zone = managed_zone(session, user, zone_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    before = {k: getattr(zone, k) for k in changes}
    for key, value in changes.items():
        setattr(zone, key, value)
    if changes:
        record(
            session,
            real_now,
            "zone.update",
            "seating_zone",
            zone_id,
            user=user,
            before=before,
            after=changes,
            request=request,
        )
        session.commit()
    return ZoneResult(server_time=now, zone=editable_zone(zone))


@router.post("/canteens/{canteen_id}/zones", status_code=201, response_model=ZoneResult, responses=RESPONSES)
def create_zone(
    canteen_id: str,
    payload: ZoneIn,
    user: StaffUser,
    request: Request,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
) -> ZoneResult:
    owner_name(session, canteen_id)
    if not can_manage_canteen(user, canteen_id):
        raise forbidden_scope("You can only add zones to your own canteens.", canteen_id=canteen_id)
    last = session.scalar(
        select(func.max(models.SeatingZone.sort_order)).where(models.SeatingZone.canteen_id == canteen_id)
    )
    zone = models.SeatingZone(
        canteen_id=canteen_id,
        name=payload.name,
        capacity=payload.capacity,
        sort_order=(last or 0) + 1,
        is_active=True,
    )
    session.add(zone)
    session.flush()
    record(
        session,
        real_now,
        "zone.create",
        "seating_zone",
        str(zone.id),
        user=user,
        after=payload.model_dump(),
        request=request,
    )
    session.commit()
    return ZoneResult(server_time=now, zone=editable_zone(zone))
