import hashlib
import json
import uuid
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Header, Response
from sqlalchemy import select

from app import models
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import DeviceDep, RealNowDep
from app.core.errors import ApiError
from app.schemas import ErrorResponse
from app.schemas_device import (
    ConfigSeat,
    ConfigZone,
    DeviceConfig,
    HeartbeatAccepted,
    HeartbeatIn,
    IgnoreArea,
    OccupancyAccepted,
    OccupancyIn,
    SimulationProfile,
    WorkerSettings,
)

router = APIRouter(tags=["devices"])

MAX_FUTURE_SKEW = timedelta(seconds=60)
DEFAULT_SETTINGS: dict[str, Any] = {
    "post_every_s": 15.0,
    "smoothing_s": 60.0,
    "dwell_s": 20.0,
    "fps": 4.0,
    "min_confidence": 0.25,
    "seated_ratio": 0.7,
    "h_stand_a": None,
    "h_stand_b": None,
    "clear_s": 30.0,
    "held_after_s": 20.0,
    "hidden_free_s": 10.0,
    "hidden_hold_s": 120.0,
    "abandoned_s": 300.0,
    "seat_radius": 0.06,
    "objects_every_s": 5.0,
}
AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}}


def current_layout(session: SessionDep, device_id: str) -> models.ZoneLayout | None:
    return session.scalars(
        select(models.ZoneLayout).where(models.ZoneLayout.device_id == device_id, models.ZoneLayout.is_current)
    ).first()


def seating_zone_ids(layout: models.ZoneLayout | None) -> list[str]:
    if layout is None:
        return []
    return [str(p["zone_id"]) for p in layout.polygons if p.get("type") == "seating" and p.get("zone_id")]


def build_config(session: SessionDep, device: models.Device) -> dict[str, Any]:
    layout = current_layout(session, device.id)
    zone_ids = seating_zone_ids(layout)
    zones = {
        str(z.id): z
        for z in session.scalars(
            select(models.SeatingZone).where(models.SeatingZone.id.in_([uuid.UUID(i) for i in zone_ids]))
        )
    }
    polygons = layout.polygons if layout else []
    config_zones = [
        ConfigZone(
            zone_id=str(p["zone_id"]),
            name=zones[str(p["zone_id"])].name,
            capacity=zones[str(p["zone_id"])].capacity,
            points=p["points"],
            seats=[ConfigSeat(**seat) for seat in p.get("seats", [])],
        )
        for p in polygons
        if p.get("type") == "seating" and str(p.get("zone_id")) in zones and zones[str(p["zone_id"])].is_active
    ]
    ignore = [
        IgnoreArea(type=p["type"], points=p["points"])
        for p in polygons
        if p.get("type") in ("queue", "walkway", "ignore")
    ]
    work = [{"area": p["area"], "points": p["points"]} for p in polygons if p.get("type") == "work" and p.get("area")]
    settings = {**DEFAULT_SETTINGS, **{k: v for k, v in device.config.items() if k in DEFAULT_SETTINGS}}
    profiles = device.config.get("profiles") if device.kind == "simulator" else None
    return {
        "device_id": device.id,
        "kind": device.kind,
        "canteen_id": device.canteen_id,
        "layout_version": layout.version if layout else None,
        "zones": [z.model_dump(mode="json") for z in config_zones],
        "ignore": [i.model_dump(mode="json") for i in ignore],
        "work": work,
        "settings": WorkerSettings(**settings).model_dump(mode="json"),
        "simulation": {k: SimulationProfile(**v).model_dump(mode="json") for k, v in profiles.items()}
        if profiles
        else None,
    }


def etag_for(config: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
    return f'"v{config["layout_version"]}-{digest}"'


@router.get(
    "/devices/{device_id}/config",
    response_model=DeviceConfig,
    responses={304: {"description": "Not modified"}, **AUTH_RESPONSES},
)
def get_device_config(
    device: DeviceDep,
    session: SessionDep,
    now: NowDep,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Any:
    config = build_config(session, device)
    etag = etag_for(config)
    if if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return DeviceConfig(server_time=now, **config)


@router.post("/devices/{device_id}/occupancy", response_model=OccupancyAccepted, responses=AUTH_RESPONSES)
def post_occupancy(
    payload: OccupancyIn, device: DeviceDep, session: SessionDep, now: NowDep, real_now: RealNowDep
) -> OccupancyAccepted:
    if payload.captured_at > real_now + MAX_FUTURE_SKEW:
        raise ApiError(
            422,
            "validation_error",
            "captured_at is more than 60 s in the future.",
            {"captured_at": payload.captured_at.isoformat()},
        )
    allowed = set(seating_zone_ids(current_layout(session, device.id)))
    unknown = [r.zone_id for r in payload.readings if r.zone_id not in allowed]
    if unknown:
        raise ApiError(
            422, "validation_error", "Readings include zones this device does not cover.", {"zone_ids": unknown}
        )
    zones = {
        str(z.id): z
        for z in session.scalars(
            select(models.SeatingZone).where(
                models.SeatingZone.id.in_([uuid.UUID(r.zone_id) for r in payload.readings])
            )
        )
    }
    captured_at = now - max(timedelta(0), real_now - payload.captured_at)
    for reading in payload.readings:
        zone = zones[reading.zone_id]
        capacity = zone.capacity
        occupied = min(reading.estimated_occupied, capacity)
        low = min(reading.occupied_low if reading.occupied_low is not None else occupied, occupied)
        high = min(max(reading.occupied_high if reading.occupied_high is not None else occupied, occupied), capacity)
        session.add(
            models.OccupancyReading(
                zone_id=zone.id,
                device_id=device.id,
                captured_at=captured_at,
                received_at=now,
                estimated_occupied=occupied,
                occupied_low=low,
                occupied_high=high,
                capacity_snapshot=capacity,
                confidence=reading.confidence,
                is_simulated=device.kind == "simulator",
            )
        )
    device.last_heartbeat_at = now
    session.commit()
    return OccupancyAccepted(server_time=now, device_id=device.id, accepted=len(payload.readings))


@router.post("/devices/{device_id}/heartbeat", response_model=HeartbeatAccepted, responses=AUTH_RESPONSES)
def post_heartbeat(payload: HeartbeatIn, device: DeviceDep, session: SessionDep, now: NowDep) -> HeartbeatAccepted:
    session.add(
        models.DeviceHeartbeat(
            device_id=device.id,
            received_at=now,
            status=payload.status,
            fps=payload.fps,
            latency_ms=payload.latency_ms,
            stream_ok=payload.stream_ok,
            message=payload.message,
        )
    )
    device.last_heartbeat_at = now
    session.commit()
    return HeartbeatAccepted(server_time=now, device_id=device.id)
