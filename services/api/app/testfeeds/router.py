import secrets
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app import models
from app.business.cameras import WAITING, check_source, is_removed, label_of, source_hint
from app.business.service import OFFLINE_AFTER
from app.business.staff_schemas import LiveLink
from app.business.staff_service import live_link
from app.core.auth import (
    ADMIN,
    CANTEEN_MANAGER,
    OWNER,
    VENUE_MANAGER,
    StaffUser,
    can_manage_canteen,
    forbidden_scope,
    require_roles,
)
from app.core.config import Settings, get_settings
from app.core.deps import NowDep, SessionDep
from app.core.device_auth import RealNowDep
from app.core.errors import ApiError, not_found
from app.routers.devices import current_layout
from app.routers.manage_config import RESPONSES, invalid
from app.services.audit import record
from app.testfeeds import schemas as s
from app.testfeeds.storage import forget_video, require_video, videos_dir
from app.testfeeds.videos import source_for, stored_name

router = APIRouter(tags=["test-feeds"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
Uploader = Annotated[models.User, Depends(require_roles(ADMIN, CANTEEN_MANAGER, OWNER, VENUE_MANAGER))]
MB = 1024 * 1024


def too_large(limit_mb: int) -> ApiError:
    return ApiError(413, "too_large", f"Test videos can be up to {limit_mb} MB. Trim the clip and try again.")


@router.post("/test-videos", response_model=s.UploadedVideo, responses=RESPONSES)
async def upload_video(
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=200)],
    user: Uploader,
    session: SessionDep,
    settings: SettingsDep,
    now: NowDep,
    real_now: RealNowDep,
) -> s.UploadedVideo:
    try:
        name = stored_name(filename)
    except ValueError as exc:
        raise invalid(str(exc)) from exc
    limit = settings.test_video_max_mb * MB
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_large(settings.test_video_max_mb)
    folder = videos_dir(settings)
    partial = folder / f".{name}.part"
    size = 0
    try:
        with partial.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise too_large(settings.test_video_max_mb)
                out.write(chunk)
        if size == 0:
            raise invalid("The video file is empty.")
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(folder / name)
    record(
        session,
        real_now,
        "testfeeds.video.upload",
        "test_video",
        name,
        user=user,
        after={"name": name, "bytes": size},
        request=request,
    )
    session.commit()
    return s.UploadedVideo(server_time=now, source=source_for(name), name=name, size_mb=round(size / MB, 1))


def feed_cameras(session: SessionDep) -> list[models.Device]:
    found = session.scalars(
        select(models.Device)
        .where(models.Device.kind == "camera", models.Device.canteen_id.in_(models.campus_canteen_ids()))
        .order_by(models.Device.id)
    )
    return [d for d in found if (d.config or {}).get("test") and not is_removed(d.config)]


def sourced_cameras(session: SessionDep) -> int:
    found = session.scalars(select(models.Device.config).where(models.Device.kind == "camera"))
    return sum(1 for config in found if config and config.get("source") and not config.get("removed"))


def feed_status(device: models.Device, beat: models.DeviceHeartbeat | None, now: datetime) -> str:
    seen = device.last_heartbeat_at
    if seen is None:
        return "starting"
    if now - seen > OFFLINE_AFTER or not device.is_enabled:
        return "offline"
    return "waiting_for_zones" if beat is not None and beat.message == WAITING else "ok"


def feed_out(session: SessionDep, device: models.Device, now: datetime) -> s.VideoFeed:
    canteen = session.get(models.Canteen, device.canteen_id)
    beat = session.scalar(
        select(models.DeviceHeartbeat)
        .where(models.DeviceHeartbeat.device_id == device.id)
        .order_by(models.DeviceHeartbeat.received_at.desc())
        .limit(1)
    )
    layout = current_layout(session, device.id)
    zone_ids = [
        uuid.UUID(str(p["zone_id"]))
        for p in (layout.polygons if layout else [])
        if p.get("type") == "seating" and p.get("zone_id")
    ]
    names = {
        z.id: z.name for z in session.scalars(select(models.SeatingZone).where(models.SeatingZone.id.in_(zone_ids)))
    }
    return s.VideoFeed(
        id=device.id,
        canteen_id=device.canteen_id,
        canteen_name=canteen.name if canteen else device.canteen_id,
        label=label_of(device.config, device.id),
        source_hint=source_hint((device.config or {}).get("source")),
        status=feed_status(device, beat, now),  # type: ignore[arg-type]
        last_seen_at=device.last_heartbeat_at,
        fps=beat.fps if beat else None,
        zones=[names[z] for z in zone_ids if z in names],
        has_layout=layout is not None,
    )


def managed_feed(session: SessionDep, user: models.User, device_id: str) -> models.Device:
    device = next((d for d in feed_cameras(session) if d.id == device_id), None)
    if device is None:
        raise not_found("Test feed", device_id)
    if not can_manage_canteen(user, device.canteen_id):
        raise forbidden_scope("You can only change test feeds for your own canteens.", device_id=device_id)
    return device


@router.get("/manage/test-feeds", response_model=s.VideoFeedList, responses=RESPONSES)
def list_feeds(user: StaffUser, session: SessionDep, settings: SettingsDep, now: NowDep) -> s.VideoFeedList:
    items = [feed_out(session, d, now) for d in feed_cameras(session) if can_manage_canteen(user, d.canteen_id)]
    return s.VideoFeedList(server_time=now, items=items, max_feeds=settings.max_cameras)


@router.post("/manage/canteens/{canteen_id}/test-feeds", response_model=s.VideoFeedResult, responses=RESPONSES)
def add_feed(
    canteen_id: str,
    payload: s.VideoFeedIn,
    user: StaffUser,
    session: SessionDep,
    settings: SettingsDep,
    now: NowDep,
    real_now: RealNowDep,
    request: Request,
) -> s.VideoFeedResult:
    canteen = session.get(models.Canteen, canteen_id)
    if canteen is None or canteen.kind != models.CANTEEN:
        raise not_found("Canteen", canteen_id)
    if not can_manage_canteen(user, canteen_id):
        raise forbidden_scope("You can only add test feeds to your own canteens.", canteen_id=canteen_id)
    if sourced_cameras(session) >= settings.max_cameras:
        limit = settings.max_cameras
        raise ApiError(409, "conflict", f"The camera computer runs up to {limit} feeds. Remove one first.")
    try:
        source = check_source(payload.source)
    except ValueError as exc:
        raise invalid(str(exc)) from exc
    require_video(settings, source)
    device = models.Device(
        id=f"cam-test-{secrets.token_hex(3)}",
        canteen_id=canteen_id,
        kind="camera",
        config={"label": payload.label.strip(), "source": source, "test": True},
    )
    session.add(device)
    session.flush()
    record(
        session,
        real_now,
        "testfeeds.feed.add",
        "device",
        device.id,
        user=user,
        after={"label": payload.label, "source": source_hint(source)},
        request=request,
    )
    session.commit()
    return s.VideoFeedResult(server_time=now, feed=feed_out(session, device, now))


@router.delete("/manage/test-feeds/{device_id}", response_model=s.VideoFeedRemoved, responses=RESPONSES)
def remove_feed(
    device_id: str,
    user: StaffUser,
    session: SessionDep,
    settings: SettingsDep,
    now: NowDep,
    real_now: RealNowDep,
    request: Request,
) -> s.VideoFeedRemoved:
    device = managed_feed(session, user, device_id)
    source = (device.config or {}).get("source")
    device.config = {"label": label_of(device.config, device.id), "test": True, "removed": True}
    device.is_enabled = False
    device.token_hash = None
    session.flush()
    forget_video(session, settings, source)
    record(
        session,
        real_now,
        "testfeeds.feed.remove",
        "device",
        device.id,
        user=user,
        before={"source": source_hint(source)},
        request=request,
    )
    session.commit()
    return s.VideoFeedRemoved(server_time=now, device_id=device.id)


@router.get("/manage/test-feeds/{device_id}/live", response_model=LiveLink, responses=RESPONSES)
def feed_live(device_id: str, user: StaffUser, session: SessionDep, now: NowDep, real_now: RealNowDep) -> LiveLink:
    return live_link(managed_feed(session, user, device_id), now, real_now)
