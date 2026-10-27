import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import models
from app.core.db import get_engine
from app.core.device_auth import hash_token, new_token

Point = tuple[float, float]


class LayoutZone(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    capacity: int = Field(ge=1, le=500)
    points: list[Point] = Field(min_length=3)


class LayoutArea(BaseModel):
    type: str = Field(pattern="^(queue|walkway|ignore)$")
    points: list[Point] = Field(min_length=3)


class LayoutFile(BaseModel):
    zones: list[LayoutZone] = Field(min_length=1)
    ignore: list[LayoutArea] = []


def _check_points(layout: LayoutFile) -> None:
    for shape in [*layout.zones, *layout.ignore]:
        for x, y in shape.points:
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("Polygon points must be normalised to the 0–1 range.")


def register(session: Session, args: argparse.Namespace) -> str | None:
    layout = LayoutFile.model_validate(json.loads(Path(args.layout).read_text(encoding="utf-8")))
    _check_points(layout)
    canteen = session.get(models.Canteen, args.canteen)
    if canteen is None:
        if not args.canteen_name:
            raise ValueError(f"Canteen '{args.canteen}' does not exist; pass --canteen-name to create it.")
        order = session.scalar(select(func.coalesce(func.max(models.Canteen.sort_order), -1))) or 0
        canteen = models.Canteen(id=args.canteen, name=args.canteen_name, sort_order=order + 1, is_sample=False)
        session.add(canteen)
        session.flush()
    existing = {
        z.name.casefold(): z
        for z in session.scalars(select(models.SeatingZone).where(models.SeatingZone.canteen_id == canteen.id))
    }
    polygons: list[dict[str, Any]] = []
    for index, zone_in in enumerate(layout.zones):
        zone = existing.get(zone_in.name.casefold())
        if zone is None:
            zone = models.SeatingZone(canteen_id=canteen.id, name=zone_in.name, sort_order=100 + index)
            session.add(zone)
        zone.capacity = zone_in.capacity
        zone.is_monitored = True
        zone.is_active = True
        session.flush()
        polygons.append({"type": "seating", "zone_id": str(zone.id), "points": [list(p) for p in zone_in.points]})
    polygons.extend({"type": a.type, "points": [list(p) for p in a.points]} for a in layout.ignore)

    device = session.get(models.Device, args.id)
    token: str | None = None
    if device is None:
        device = models.Device(id=args.id, canteen_id=canteen.id, kind="camera", config={})
        session.add(device)
        token = new_token()
    elif args.rotate:
        token = new_token()
    if token is not None:
        device.token_hash = hash_token(token)
    device.canteen_id = canteen.id
    device.is_enabled = True
    settings = dict(device.config)
    for key in ("dwell_s", "post_every_s", "smoothing_s", "fps"):
        value = getattr(args, key)
        if value is not None:
            settings[key] = value
    device.config = settings
    session.flush()

    version = (
        session.scalar(select(func.max(models.ZoneLayout.version)).where(models.ZoneLayout.device_id == device.id)) or 0
    ) + 1
    session.execute(update(models.ZoneLayout).where(models.ZoneLayout.device_id == device.id).values(is_current=False))
    session.add(models.ZoneLayout(device_id=device.id, version=version, polygons=polygons, is_current=True))
    session.commit()
    print(f"Registered {device.id} in {canteen.name} with {len(layout.zones)} zone(s), layout version {version}.")
    return token


def rotate(session: Session, device_id: str) -> str:
    device = session.get(models.Device, device_id)
    if device is None:
        raise ValueError(f"Device '{device_id}' does not exist.")
    token = new_token()
    device.token_hash = hash_token(token)
    session.commit()
    return token


def list_devices(session: Session) -> None:
    for device in session.scalars(select(models.Device).order_by(models.Device.canteen_id, models.Device.id)):
        state = "enabled" if device.is_enabled else "disabled"
        seen = device.last_heartbeat_at.isoformat(timespec="seconds") if device.last_heartbeat_at else "never"
        print(f"{device.id:<20} {device.kind:<10} canteen={device.canteen_id:<8} {state:<9} last seen {seen}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage DineMate camera devices.")
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register", help="create or update a camera device and its zone layout")
    reg.add_argument("--id", required=True, help="device id, e.g. cam-webcam")
    reg.add_argument("--canteen", required=True, help="canteen id the zones belong to")
    reg.add_argument("--canteen-name", help="create the canteen with this name if it does not exist")
    reg.add_argument("--layout", required=True, help="layout JSON written by the vision zone tool")
    reg.add_argument("--rotate", action="store_true", help="issue a new token for an existing device")
    reg.add_argument("--dwell-s", dest="dwell_s", type=float)
    reg.add_argument("--post-every-s", dest="post_every_s", type=float)
    reg.add_argument("--smoothing-s", dest="smoothing_s", type=float)
    reg.add_argument("--fps", type=float)
    tok = sub.add_parser("token", help="issue a new token for a device")
    tok.add_argument("--id", required=True)
    sub.add_parser("list", help="list devices")
    args = parser.parse_args(argv)
    try:
        with Session(get_engine()) as session:
            if args.command == "register":
                token = register(session, args)
            elif args.command == "token":
                token = rotate(session, args.id)
            else:
                list_devices(session)
                return 0
    except (ValueError, ValidationError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if token:
        print(f"Device token (shown once, store it in the worker's .env): {token}")
    else:
        print("Existing token kept. Use --rotate or the 'token' command for a new one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
