import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (CheckConstraint("kind IN ('camera', 'simulator')", name="kind"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"), index=True)
    kind: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class ZoneLayout(Base):
    __tablename__ = "zone_layouts"
    __table_args__ = (
        UniqueConstraint("device_id", "version", name="uq_zone_layouts_device_version"),
        Index("one_current_layout_per_device", "device_id", unique=True, postgresql_where=text("is_current")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    polygons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    reference_image_url: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeviceHeartbeat(Base):
    __tablename__ = "device_heartbeats"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'degraded', 'error')", name="status"),
        Index("ix_device_heartbeats_device_received", "device_id", text("received_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)
    fps: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    stream_ok: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    message: Mapped[str | None] = mapped_column(Text)


class OccupancyReading(Base):
    __tablename__ = "occupancy_readings"
    __table_args__ = (
        CheckConstraint("estimated_occupied >= 0", name="non_negative"),
        CheckConstraint(
            "occupied_low <= estimated_occupied AND estimated_occupied <= occupied_high", name="range_order"
        ),
        CheckConstraint("confidence IN ('high', 'medium', 'low')", name="confidence"),
        Index("ix_occupancy_readings_zone_captured", "zone_id", text("captured_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seating_zones.id"))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    estimated_occupied: Mapped[int] = mapped_column(Integer)
    occupied_low: Mapped[int] = mapped_column(Integer)
    occupied_high: Mapped[int] = mapped_column(Integer)
    capacity_snapshot: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(Text)
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
