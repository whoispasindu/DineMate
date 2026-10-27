import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

LEVELS = "'normal', 'busy', 'crowded', 'near_capacity'"


class CrowdingThreshold(Base):
    __tablename__ = "crowding_thresholds"
    __table_args__ = (
        CheckConstraint(
            "busy_pct < crowded_pct AND crowded_pct < near_capacity_pct AND near_capacity_pct <= 100", name="order"
        ),
        CheckConstraint(f"alert_from IN ({LEVELS})", name="alert_from"),
    )

    zone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seating_zones.id", ondelete="CASCADE"), primary_key=True)
    busy_pct: Mapped[float] = mapped_column(Numeric(5, 2), server_default="60")
    crowded_pct: Mapped[float] = mapped_column(Numeric(5, 2), server_default="80")
    near_capacity_pct: Mapped[float] = mapped_column(Numeric(5, 2), server_default="95")
    hysteresis_pct: Mapped[float] = mapped_column(Numeric(5, 2), server_default="5")
    dwell_seconds: Mapped[int] = mapped_column(Integer, server_default="120")
    alert_from: Mapped[str] = mapped_column(Text, server_default="crowded")


class ZoneCrowdState(Base):
    __tablename__ = "zone_crowd_states"
    __table_args__ = (
        CheckConstraint(f"level IN ({LEVELS})", name="level"),
        CheckConstraint(f"candidate IS NULL OR candidate IN ({LEVELS})", name="candidate"),
    )

    zone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seating_zones.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[str] = mapped_column(Text, server_default="normal")
    candidate: Mapped[str | None] = mapped_column(Text)
    candidate_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StaffAlert(Base):
    __tablename__ = "staff_alerts"
    __table_args__ = (
        CheckConstraint("type IN ('crowding', 'data_stale', 'sensor_offline')", name="type"),
        CheckConstraint("status IN ('open', 'acknowledged', 'suspended', 'resolved')", name="status"),
        CheckConstraint(f"level IS NULL OR level IN ({LEVELS})", name="level"),
        CheckConstraint("zone_id IS NOT NULL OR device_id IS NOT NULL", name="has_subject"),
        Index(
            "one_active_alert_per_subject",
            "type",
            text("coalesce(zone_id::text, device_id)"),
            unique=True,
            postgresql_where=text("status <> 'resolved'"),
        ),
        Index("ix_staff_alerts_opened_at", text("opened_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(Text)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seating_zones.id", ondelete="CASCADE"))
    device_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("devices.id", ondelete="CASCADE"))
    level: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
