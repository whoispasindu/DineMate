import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app import models
from app.business import camera_schemas as cs
from app.business.auth import BusinessUser, venue_for
from app.business.cameras import check_source, is_removed, label_of, source_hint
from app.business.router import RESPONSES
from app.core.config import Settings, get_settings
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import DeviceDep, RealNowDep, hash_token, new_token
from app.core.errors import ApiError, not_found
from app.routers.devices import AUTH_RESPONSES, current_layout
from app.routers.manage_zones import (
    CONFLICT,
    device_layout,
    editable_zone,
    save_version,
    sync_seat_capacity,
    validate_polygons,
)
from app.schemas_config import DeviceLayout, LayoutIn
from app.services.audit import record
from app.testfeeds.storage import forget_video, require_video

router = APIRouter(prefix="/business", tags=["business-cameras"])
devices = APIRouter(tags=["business-cameras"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


def invalid(message: str, **details: Any) -> ApiError:
    return ApiError(422, "validation_error", message, details or None)


def camera_out(device: models.Device) -> cs.CameraOut:
    return cs.CameraOut(
        id=device.id,
        venue_id=device.canteen_id,
        label=label_of(device.config, device.id),
        source_hint=source_hint((device.config or {}).get("source")),
        enabled=device.is_enabled,
    )


def camera_for(session: SessionDep, user: models.User, device_id: str) -> models.Device:
    device = session.get(models.Device, device_id)
    if device is None or device.kind != "camera" or is_removed(device.config):
        raise not_found("Camera", device_id)
    venue_for(session, user, device.canteen_id)
    return device


def organization_cameras(session: SessionDep, organization_id: str) -> list[models.Device]:
    venues = select(models.Canteen.id).where(
        models.Canteen.organization_id == organization_id, models.Canteen.kind == models.VENUE
    )
    found = session.scalars(
        select(models.Device)
        .where(models.Device.canteen_id.in_(venues), models.Device.kind == "camera")
        .order_by(models.Device.id)
    )
    return [d for d in found if not is_removed(d.config)]


def checked_source(settings: Settings, source: str) -> str:
    try:
        value = check_source(source)
    except ValueError as exc:
        raise invalid(str(exc)) from exc
    return require_video(settings, value)


def scope_cameras(session: SessionDep, hub: models.Device) -> list[models.Device]:
    if hub.kind != "hub":
        raise not_found("Hub", hub.id)
    if (hub.config or {}).get("scope") == "all":
        found = session.scalars(select(models.Device).where(models.Device.kind == "camera").order_by(models.Device.id))
        return [d for d in found if (d.config or {}).get("source") and not is_removed(d.config)]
    venue = session.get(models.Canteen, hub.canteen_id)
    if venue is None or venue.organization_id is None:
        raise not_found("Hub", hub.id)
    return organization_cameras(session, venue.organization_id)


@router.post("/venues/{venue_id}/cameras", response_model=cs.CameraResult, responses=RESPONSES)
def add_camera(
    venue_id: str,
    payload: cs.CameraIn,
    user: BusinessUser,
    session: SessionDep,
    settings: SettingsDep,
    now: NowDep,
    real_now: RealNowDep,
    request: Request,
) -> cs.CameraResult:
    venue = venue_for(session, user, venue_id)
    if len(organization_cameras(session, user.organization_id)) >= settings.max_cameras:
        raise ApiError(409, "conflict", f"This computer runs up to {settings.max_cameras} cameras.")
    source = checked_source(settings, payload.source)
    device = models.Device(
        id=f"cam-{secrets.token_hex(3)}",
        canteen_id=venue.id,
        kind="camera",
        config={"label": payload.label.strip(), "source": source},
    )
    session.add(device)
    session.flush()
    record(
        session,
        real_now,
        "business.camera.add",
        "device",
        device.id,
        user=user,
        after={"label": payload.label, "source": source_hint(source)},
        request=request,
    )
    session.commit()
    return cs.CameraResult(server_time=now, camera=camera_out(device))


@router.patch("/cameras/{device_id}", response_model=cs.CameraResult, responses=RESPONSES)
def update_camera(
    device_id: str,
    payload: cs.CameraPatch,
    user: BusinessUser,
    session: SessionDep,
    settings: SettingsDep,
    now: NowDep,
    real_now: RealNowDep,
    request: Request,
) -> cs.CameraResult:
    device = camera_for(session, user, device_id)
    before = camera_out(device).model_dump()
    config = dict(device.config or {})
    old_source = config.get("source")
    if payload.label is not None:
        config["label"] = payload.label.strip()
    if payload.source is not None:
        config["source"] = checked_source(settings, payload.source)
        config.pop("stream_url", None)
    if payload.enabled is not None:
        device.is_enabled = payload.enabled
    device.config = config
    session.flush()
    if config.get("source") != old_source:
        forget_video(session, settings, old_source)
    record(
        session,
        real_now,
        "business.camera.update",
        "device",
        device.id,
        user=user,
        before=before,
        after=camera_out(device).model_dump(),
        request=request,
    )
    session.commit()
    return cs.CameraResult(server_time=now, camera=camera_out(device))


@router.delete("/cameras/{device_id}", response_model=cs.CameraRemoved, responses=RESPONSES)
def remove_camera(
    device_id: str,
    user: BusinessUser,
    session: SessionDep,
    settings: SettingsDep,
    now: NowDep,
    real_now: RealNowDep,
    request: Request,
) -> cs.CameraRemoved:
    device = camera_for(session, user, device_id)
    before = camera_out(device).model_dump()
    source = (device.config or {}).get("source")
    device.config = {"label": label_of(device.config, device.id), "removed": True}
    device.is_enabled = False
    device.token_hash = None
    session.flush()
    forget_video(session, settings, source)
    record(session, real_now, "business.camera.remove", "device", device.id, user=user, before=before, request=request)
    session.commit()
    return cs.CameraRemoved(server_time=now, device_id=device.id)


@router.get("/cameras/{device_id}/layout", response_model=DeviceLayout, responses=RESPONSES)
def get_camera_layout(device_id: str, user: BusinessUser, session: SessionDep, now: NowDep) -> DeviceLayout:
    return device_layout(session, camera_for(session, user, device_id), now)


@router.put("/cameras/{device_id}/layout", response_model=DeviceLayout, responses=CONFLICT)
def put_camera_layout(
    device_id: str,
    payload: LayoutIn,
    user: BusinessUser,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
    request: Request,
) -> DeviceLayout:
    device = camera_for(session, user, device_id)
    layout = current_layout(session, device.id)
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
    sync_seat_capacity(session, polygons)
    record(
        session,
        real_now,
        "business.layout.save",
        "device",
        device.id,
        user=user,
        before={"version": current},
        after={
            "version": version,
            "polygons": len(polygons),
            "seats": sum(len(p.get("seats") or []) for p in polygons),
        },
        request=request,
    )
    session.commit()
    return device_layout(session, device, now)


@router.post("/venues/{venue_id}/areas", response_model=cs.AreaResult, responses=RESPONSES)
def add_area(
    venue_id: str,
    payload: cs.AreaIn,
    user: BusinessUser,
    session: SessionDep,
    now: NowDep,
    real_now: RealNowDep,
    request: Request,
) -> cs.AreaResult:
    venue = venue_for(session, user, venue_id)
    name = payload.name.strip()
    taken = session.scalar(
        select(models.SeatingZone.id).where(
            models.SeatingZone.canteen_id == venue.id, func.lower(models.SeatingZone.name) == name.lower()
        )
    )
    if taken is not None:
        raise ApiError(409, "conflict", f"There is already an area called {name}.")
    last = session.scalar(
        select(func.max(models.SeatingZone.sort_order)).where(models.SeatingZone.canteen_id == venue.id)
    )
    zone = models.SeatingZone(
        canteen_id=venue.id, name=name, capacity=1, sort_order=(last or 0) + 1, is_active=True, is_monitored=True
    )
    session.add(zone)
    session.flush()
    record(
        session,
        real_now,
        "business.area.add",
        "seating_zone",
        str(zone.id),
        user=user,
        after={"name": name},
        request=request,
    )
    session.commit()
    return cs.AreaResult(server_time=now, zone=editable_zone(zone))


@devices.get("/devices/{device_id}/hub/cameras", response_model=cs.HubCameras, responses=AUTH_RESPONSES)
def hub_cameras(device: DeviceDep, session: SessionDep, now: NowDep, real_now: RealNowDep) -> cs.HubCameras:
    found = scope_cameras(session, device)
    device.last_heartbeat_at = real_now
    cameras = [
        cs.HubCamera(
            device_id=d.id,
            venue_id=d.canteen_id,
            label=label_of(d.config, d.id),
            source=str((d.config or {}).get("source") or ""),
            enabled=d.is_enabled,
        )
        for d in found
        if (d.config or {}).get("source")
    ]
    session.commit()
    return cs.HubCameras(server_time=now, hub_id=device.id, cameras=cameras)


@devices.post("/devices/{device_id}/hub/tokens", response_model=cs.HubTokens, responses=AUTH_RESPONSES)
def hub_tokens(
    payload: cs.HubTokensIn, device: DeviceDep, session: SessionDep, now: NowDep, real_now: RealNowDep
) -> cs.HubTokens:
    mine = {d.id: d for d in scope_cameras(session, device) if d.is_enabled}
    unknown = [i for i in payload.device_ids if i not in mine]
    if unknown:
        raise not_found("Camera", unknown[0])
    tokens = []
    for device_id in dict.fromkeys(payload.device_ids):
        token = new_token()
        mine[device_id].token_hash = hash_token(token)
        tokens.append(cs.HubToken(device_id=device_id, token=token))
    record(
        session,
        real_now,
        "business.hub.tokens",
        "device",
        device.id,
        device_id=device.id,
        after={"cameras": list(dict.fromkeys(payload.device_ids))},
    )
    session.commit()
    return cs.HubTokens(server_time=now, tokens=tokens)
