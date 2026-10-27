import logging
import random
import sys
import time as systime
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models
from app.core import clock
from app.core.config import get_settings
from app.core.db import get_engine
from app.services.views import latest_readings

DRIFT = 4
STEPS = (-1, 0, 0, 1)

log = logging.getLogger("dinemate.sim")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def tick(session: Session, now: datetime, rng: random.Random) -> int:
    devices = session.scalars(
        select(models.Device).where(models.Device.kind == "simulator", models.Device.is_enabled)
    ).all()
    written = 0
    for device in devices:
        layout = session.scalars(
            select(models.ZoneLayout).where(models.ZoneLayout.device_id == device.id, models.ZoneLayout.is_current)
        ).first()
        if layout is None:
            continue
        zone_ids = [p["zone_id"] for p in layout.polygons if p.get("type") == "seating" and p.get("zone_id")]
        zones = {
            str(z.id): z for z in session.scalars(select(models.SeatingZone).where(models.SeatingZone.id.in_(zone_ids)))
        }
        previous = latest_readings(session, [z.id for z in zones.values()])
        for zone_id, zone in zones.items():
            profile = device.config.get("profiles", {}).get(zone_id)
            if profile is None or not zone.is_active:
                continue
            base, below, above = int(profile["base"]), int(profile["below"]), int(profile["above"])
            last = previous.get(zone.id)
            occupied = _clamp((last.occupied if last else base) + rng.choice(STEPS), base - DRIFT, base + DRIFT)
            occupied = _clamp(occupied, 0, zone.capacity)
            session.add(
                models.OccupancyReading(
                    zone_id=zone.id,
                    device_id=device.id,
                    captured_at=now,
                    estimated_occupied=occupied,
                    occupied_low=max(0, occupied - below),
                    occupied_high=min(zone.capacity, occupied + above),
                    capacity_snapshot=zone.capacity,
                    confidence="medium",
                    is_simulated=True,
                )
            )
            written += 1
        device.last_heartbeat_at = now
    session.commit()
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    rng = random.Random()
    log.info(
        "Occupancy simulator started; posting every %.0f s (all readings marked is_simulated)",
        settings.simulator_interval_s,
    )
    while True:
        try:
            with Session(get_engine()) as session:
                written = tick(session, clock.now(settings), rng)
            log.info("wrote %d simulated readings", written)
        except SQLAlchemyError as exc:
            log.warning("database unavailable, retrying: %s", exc.__class__.__name__)
        systime.sleep(settings.simulator_interval_s)


if __name__ == "__main__":
    sys.exit(main())
