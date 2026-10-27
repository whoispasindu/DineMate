import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import PERIOD_VALUES, WEEKDAY_CHECK, Base, Timestamps

SHOP_KINDS = ("rice", "kottu", "short_eats", "tea", "noodles", "bakery", "drinks")
MENU_CATEGORIES = ("rice", "kottu", "short_eats", "drinks")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Shop(Timestamps, Base):
    __tablename__ = "shops"
    __table_args__ = (CheckConstraint(_in("kind", SHOP_KINDS), name="kind"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, server_default="rice")
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    temporarily_closed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closure_reason: Mapped[str | None] = mapped_column(Text)
    menu_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    hours: Mapped[list["ShopHours"]] = relationship(order_by=lambda: [ShopHours.weekday, ShopHours.opens])
    exceptions: Mapped[list["ShopHourException"]] = relationship()


class ShopHours(Base):
    __tablename__ = "shop_hours"
    __table_args__ = (
        CheckConstraint(WEEKDAY_CHECK, name="weekday"),
        CheckConstraint("opens < closes", name="opens_before_closes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    opens: Mapped[time] = mapped_column(Time)
    closes: Mapped[time] = mapped_column(Time)


class ShopHourException(Base):
    __tablename__ = "shop_hour_exceptions"
    __table_args__ = (
        CheckConstraint(
            "is_closed OR (opens IS NOT NULL AND closes IS NOT NULL AND opens < closes)", name="closed_or_valid_hours"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    is_closed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    opens: Mapped[time | None] = mapped_column(Time)
    closes: Mapped[time | None] = mapped_column(Time)
    reason: Mapped[str | None] = mapped_column(Text)


class MenuItem(Timestamps, Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("price_cents >= 0 AND price_cents <= 10000000", name="price_range"),
        CheckConstraint(f"category IS NULL OR {_in('category', MENU_CATEGORIES)}", name="category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)
    dietary_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    is_available: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    availability_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    periods: Mapped[list["MenuItemPeriod"]] = relationship(cascade="all, delete-orphan")


class MenuItemPeriod(Base):
    __tablename__ = "menu_item_periods"
    __table_args__ = (CheckConstraint(_in("period", PERIOD_VALUES), name="period"),)

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"), primary_key=True)
    period: Mapped[str] = mapped_column(Text, primary_key=True)
