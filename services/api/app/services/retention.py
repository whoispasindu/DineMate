from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app import models
from app.core.config import Settings

TOKEN_GRACE = timedelta(days=1)


def purge_old_data(session: Session, now: datetime, real_now: datetime, settings: Settings) -> dict[str, int]:
    readings = now - timedelta(days=settings.readings_retention_days)
    beats = now - timedelta(days=settings.heartbeat_retention_days)
    lock = timedelta(minutes=settings.login_lock_minutes)
    ss, lt = models.SeatSession, models.LoginThrottle
    steps = {
        "occupancy_readings": delete(models.OccupancyReading).where(models.OccupancyReading.captured_at < readings),
        "seat_sessions": delete(ss).where(ss.ended_at.is_not(None), ss.ended_at < readings),
        "device_heartbeats": delete(models.DeviceHeartbeat).where(models.DeviceHeartbeat.received_at < beats),
        "refresh_tokens": delete(models.RefreshToken).where(models.RefreshToken.expires_at < real_now - TOKEN_GRACE),
        "login_throttles": delete(lt).where(lt.first_failed_at < real_now - lock - lock),
    }
    return {name: session.execute(step).rowcount or 0 for name, step in steps.items()}  # type: ignore[attr-defined]
