import uuid
from datetime import date, time

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Text, Time, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import PERIOD_VALUES, WEEKDAY_CHECK, Base

PERIOD_CHECK = f"period IN ({', '.join(repr(p) for p in PERIOD_VALUES)})"


class MealSchedule(Base):
    __tablename__ = "meal_schedules"
    __table_args__ = (
        CheckConstraint(WEEKDAY_CHECK, name="weekday"),
        CheckConstraint(PERIOD_CHECK, name="period"),
        CheckConstraint("starts < ends", name="starts_before_ends"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canteen_id: Mapped[str | None] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(Text)
    starts: Mapped[time] = mapped_column(Time)
    ends: Mapped[time] = mapped_column(Time)


class ScheduleOverride(Base):
    __tablename__ = "schedule_overrides"
    __table_args__ = (
        CheckConstraint(f"period IS NULL OR {PERIOD_CHECK}", name="period"),
        CheckConstraint(
            "is_cancelled OR (period IS NOT NULL AND starts IS NOT NULL AND ends IS NOT NULL AND starts < ends)",
            name="cancelled_or_valid_times",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canteen_id: Mapped[str | None] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    period: Mapped[str | None] = mapped_column(Text)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    starts: Mapped[time | None] = mapped_column(Time)
    ends: Mapped[time | None] = mapped_column(Time)
    reason: Mapped[str | None] = mapped_column(Text)
