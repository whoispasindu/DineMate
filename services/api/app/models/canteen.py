import uuid
from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Select, String, Text, Time, Uuid, select, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import WEEKDAY_CHECK, Base, Timestamps
from app.models.organization import CAMPUS_ORG

CANTEEN = "canteen"
VENUE = "venue"
VENUE_PREFIX = "v-"


def is_venue_id(canteen_id: str) -> bool:
    return canteen_id.startswith(VENUE_PREFIX)


class Canteen(Timestamps, Base):
    __tablename__ = "canteens"
    __table_args__ = (
        CheckConstraint("kind IN ('canteen', 'venue')", name="kind"),
        CheckConstraint("(kind = 'venue') = (id LIKE 'v-%')", name="venue_id_prefix"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), server_default=CAMPUS_ORG, index=True)
    kind: Mapped[str] = mapped_column(Text, server_default=CANTEEN)
    name: Mapped[str] = mapped_column(Text)
    location_note: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, server_default="Asia/Colombo")
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    zones: Mapped[list["SeatingZone"]] = relationship(back_populates="canteen", order_by="SeatingZone.sort_order")
    hours: Mapped[list["CanteenHours"]] = relationship(order_by="CanteenHours.opens")


class CanteenHours(Base):
    __tablename__ = "canteen_hours"
    __table_args__ = (
        CheckConstraint(WEEKDAY_CHECK, name="weekday"),
        CheckConstraint("opens < closes", name="opens_before_closes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    opens: Mapped[time] = mapped_column(Time)
    closes: Mapped[time] = mapped_column(Time)


class WalkingTime(Base):
    __tablename__ = "walking_times"
    __table_args__ = (CheckConstraint("minutes > 0", name="positive_minutes"),)

    from_canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), primary_key=True)
    to_canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), primary_key=True)
    minutes: Mapped[int] = mapped_column(Integer)


class SeatingZone(Timestamps, Base):
    __tablename__ = "seating_zones"
    __table_args__ = (CheckConstraint("capacity > 0 AND capacity <= 500", name="capacity_range"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    capacity: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    is_monitored: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    canteen: Mapped[Canteen] = relationship(back_populates="zones")


def campus_canteen_ids() -> Select[tuple[str]]:
    return select(Canteen.id).where(Canteen.kind == CANTEEN)
