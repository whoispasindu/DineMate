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


BUSINESS_TABLES = ["table_visits", "venue_tables"]
