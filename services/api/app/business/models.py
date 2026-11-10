import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

TABLE_SHAPES = ("round", "rect")


class VenueTable(Base):
    __tablename__ = "venue_tables"
    __table_args__ = (
        UniqueConstraint("venue_id", "name", name="uq_venue_tables_venue_name"),
        CheckConstraint("shape IN ('round', 'rect')", name="shape"),
        CheckConstraint("x >= 0 AND y >= 0 AND w > 0 AND h > 0 AND x + w <= 1 AND y + h <= 1", name="inside_floor"),
        CheckConstraint("cardinality(seat_ids) BETWEEN 1 AND 20", name="seat_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seating_zones.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    shape: Mapped[str] = mapped_column(Text, server_default="rect")
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    w: Mapped[float] = mapped_column(Float)
    h: Mapped[float] = mapped_column(Float)
    seat_ids: Mapped[list[str]] = mapped_column(ARRAY(Text))
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TableVisit(Base):
    __tablename__ = "table_visits"
    __table_args__ = (
        CheckConstraint("party_size > 0", name="party_size"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ends_after_start"),
        Index("ix_table_visits_table_started", "table_id", "started_at"),
        Index("one_open_visit_per_table", "table_id", unique=True, postgresql_where=text("ended_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venue_tables.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    party_size: Mapped[int] = mapped_column(Integer)
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


STAFF_METHODS = ("face", "badge")
WORK_AREAS = ("counter", "kitchen", "floor")


class StaffMember(Base):
    __tablename__ = "staff_members"
    __table_args__ = (
        UniqueConstraint("venue_id", "display_name", name="uq_staff_members_venue_name"),
        Index(
            "uq_staff_members_badge",
            "venue_id",
            "badge_code",
            unique=True,
            postgresql_where=text("badge_code IS NOT NULL"),
        ),
        Index(
            "uq_staff_members_till",
            "venue_id",
            "till_code",
            unique=True,
            postgresql_where=text("till_code IS NOT NULL"),
        ),
        CheckConstraint("method IN ('face', 'badge')", name="method"),
        CheckConstraint("badge_code IS NULL OR badge_code BETWEEN 0 AND 249", name="badge_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(Text)
    role_label: Mapped[str] = mapped_column(Text, server_default="")
    method: Mapped[str] = mapped_column(Text, server_default="badge")
    badge_code: Mapped[int | None] = mapped_column(Integer)
    till_code: Mapped[str | None] = mapped_column(Text)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_version: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FaceTemplate(Base):
    __tablename__ = "face_templates"

    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_members.id", ondelete="CASCADE"), primary_key=True)
    sealed: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StaffPresence(Base):
    __tablename__ = "staff_presence"
    __table_args__ = (
        CheckConstraint("area IN ('counter', 'kitchen', 'floor')", name="area"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ends_after_start"),
        Index("ix_staff_presence_staff_started", "staff_id", "started_at"),
        Index("one_open_presence", "staff_id", "area", unique=True, postgresql_where=text("ended_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_members.id", ondelete="CASCADE"))
    area: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class QueueReading(Base):
    __tablename__ = "queue_readings"
    __table_args__ = (
        CheckConstraint("people >= 0", name="non_negative"),
        Index("ix_queue_readings_venue_at", "venue_id", "at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    venue_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    people: Mapped[int | None] = mapped_column(Integer)
    counter_people: Mapped[int | None] = mapped_column(Integer)
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class TillOrder(Base):
    __tablename__ = "till_orders"
    __table_args__ = (
        UniqueConstraint("venue_id", "order_ref", name="uq_till_orders_venue_ref"),
        Index("ix_till_orders_venue_at", "venue_id", "at"),
        CheckConstraint("total >= 0", name="non_negative_total"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    venue_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"))
    order_ref: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cashier_code: Mapped[str | None] = mapped_column(Text)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_members.id", ondelete="SET NULL"), index=True)
    total: Mapped[float] = mapped_column(Numeric(12, 2))
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class TillItem(Base):
    __tablename__ = "till_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="positive_qty"),
        CheckConstraint("unit_price >= 0", name="non_negative_price"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("till_orders.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))


BUSINESS_TABLES = [
    "till_items",
    "till_orders",
    "queue_readings",
    "staff_presence",
    "face_templates",
    "staff_members",
    "table_visits",
    "venue_tables",
]
