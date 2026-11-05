import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SEAT_STATES = "state IN ('free', 'occupied', 'held', 'unknown')"


class SeatState(Base):
    __tablename__ = "seat_states"
    __table_args__ = (CheckConstraint(SEAT_STATES, name="state"),)

    zone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seating_zones.id", ondelete="CASCADE"), primary_key=True)
    seat_id: Mapped[str] = mapped_column(Text, primary_key=True)
    state: Mapped[str] = mapped_column(Text)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    free_soon: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SeatSession(Base):
    __tablename__ = "seat_sessions"
    __table_args__ = (
        CheckConstraint(SEAT_STATES, name="state"),
        Index("ix_seat_sessions_zone_started", "zone_id", "started_at"),
        Index("ix_seat_sessions_open", "zone_id", "seat_id", postgresql_where=sql_text("ended_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zone_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seating_zones.id", ondelete="CASCADE"))
    seat_id: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))


class ZoneSeatStatus(Base):
    __tablename__ = "zone_seat_status"
    __table_args__ = (
        CheckConstraint("free >= 0 AND occupied >= 0 AND held >= 0 AND unknown >= 0", name="non_negative"),
    )

    zone_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seating_zones.id", ondelete="CASCADE"), primary_key=True
    )
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.id", ondelete="CASCADE"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    free: Mapped[int] = mapped_column(Integer)
    occupied: Mapped[int] = mapped_column(Integer)
    held: Mapped[int] = mapped_column(Integer)
    unknown: Mapped[int] = mapped_column(Integer)
    free_soon: Mapped[int] = mapped_column(Integer, server_default="0")
    standing: Mapped[int] = mapped_column(Integer, server_default="0")
    crowded: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
