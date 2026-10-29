import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

SOURCE_KINDS = ("simulator", "approved_integration")
EVENT_TYPES = ("fire_alarm", "evacuation", "test_notice", "integration_offline")
SEVERITIES = ("critical", "warning", "info")
STATUSES = ("active", "acknowledged", "resolved")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class SafetySource(Base):
    __tablename__ = "safety_sources"
    __table_args__ = (CheckConstraint(_in("kind", SOURCE_KINDS), name="kind"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SafetyEvent(Base):
    __tablename__ = "safety_events"
    __table_args__ = (
        UniqueConstraint("source_id", "external_event_id", name="uq_safety_events_source_external"),
        CheckConstraint(_in("event_type", EVENT_TYPES), name="event_type"),
        CheckConstraint(_in("severity", SEVERITIES), name="severity"),
        CheckConstraint(_in("status", STATUSES), name="status"),
        CheckConstraint("status <> 'resolved' OR resolution_note IS NOT NULL", name="resolved_with_note"),
        Index("ix_safety_events_status_received", "status", text("received_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(ForeignKey("safety_sources.id"))
    external_event_id: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    canteen_id: Mapped[str | None] = mapped_column(ForeignKey("canteens.id"))
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seating_zones.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_simulation: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    repeat_count: Mapped[int] = mapped_column(Integer, server_default="1")
    note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)

    source: Mapped[SafetySource] = relationship(lazy="joined")
    acks: Mapped[list["SafetyEventAck"]] = relationship(
        order_by=lambda: SafetyEventAck.acknowledged_at, lazy="selectin"
    )


class SafetyEventAck(Base):
    __tablename__ = "safety_event_acks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("safety_events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    user_name: Mapped[str] = mapped_column(Text)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)


class SafetyInstruction(Base):
    __tablename__ = "safety_instructions"
    __table_args__ = (CheckConstraint(_in("event_type", EVENT_TYPES), name="event_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canteen_id: Mapped[str | None] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    approved_by_name: Mapped[str] = mapped_column(Text)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


SAFETY_TABLES = ["safety_event_acks", "safety_events", "safety_instructions", "safety_sources"]
