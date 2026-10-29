from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, PlainSerializer, StringConstraints

from app.schemas import MealPeriod, Schema, Shop, Timestamped

MenuCategory = Literal["rice", "kottu", "short_eats", "drinks"]
DietaryTag = Literal["vegetarian"]
PendingChange = Literal["none", "new", "edit", "delete"]
ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Price = Annotated[
    Decimal, Field(ge=0, le=100_000, max_digits=8, decimal_places=2), PlainSerializer(float, return_type=float)
]


class WeeklyHours(Schema):
    weekday: int = Field(ge=0, le=6)
    opens: time
    closes: time


class HoursException(Schema):
    date: date
    is_closed: bool
    opens: time | None = None
    closes: time | None = None
    reason: Reason | None = None


class ShopHoursIn(Schema):
    weekly: list[WeeklyHours] = Field(max_length=42)
    exceptions: list[HoursException] = Field(max_length=60)


class ClosureIn(Schema):
    until: datetime | None
    reason: Reason | None = None


class MenuItemFields(Schema):
    name: ItemName
    price_lkr: Price
    category: MenuCategory | None = None
    dietary_tags: list[DietaryTag] = Field(default_factory=list, max_length=4)
    periods: list[MealPeriod] = Field(min_length=1, max_length=3)


class MenuItemPatch(Schema):
    name: ItemName | None = None
    price_lkr: Price | None = None
    category: MenuCategory | None = None
    dietary_tags: list[DietaryTag] | None = Field(default=None, max_length=4)
    periods: list[MealPeriod] | None = Field(default=None, min_length=1, max_length=3)


class AvailabilityIn(Schema):
    is_available: bool


class EditableMenuItem(Schema):
    id: str
    live: MenuItemFields | None
    draft: MenuItemFields | None
    pending: PendingChange
    is_available: bool
    availability_updated_at: datetime


class ManagedShop(Schema):
    shop: Shop
    pending_changes: int


class ManagedShopList(Timestamped):
    items: list[ManagedShop]


class ShopEditor(Timestamped):
    shop: Shop
    weekly: list[WeeklyHours]
    exceptions: list[HoursException]
    temporarily_closed_until: datetime | None
    closure_reason: str | None
    items: list[EditableMenuItem]
    pending_changes: int


class AvailabilityResult(Timestamped):
    item: EditableMenuItem
